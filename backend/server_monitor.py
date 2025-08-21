"""
Server monitoring service with background checks.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
import httpx

from backend.config import settings
from backend.database import get_database_url
from backend.models import Server, ServerStatus, Alert, AlertLevel
from backend.glances_client import GlancesClient
from backend.telegram_client import TelegramClient

logger = logging.getLogger(__name__)

# Database setup for monitor
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


class ServerMonitorService:
    """Background server monitoring service."""
    
    def __init__(self):
        self.glances_client = GlancesClient()
        self.telegram_client = TelegramClient()
        self.server_failure_counts: Dict[int, int] = {}
        self.server_alert_states: Dict[str, Dict[int, bool]] = {
            'cpu_high': {},
            'memory_high': {},
            'disk_high': {},
            'unreachable': {}
        }
        self.running = False
        self.monitor_task = None
        
        # Alert thresholds
        self.CPU_THRESHOLD = 85.0  # %
        self.MEMORY_THRESHOLD = 90.0  # %
        self.DISK_THRESHOLD = 85.0  # %
    
    async def start(self):
        """Start the monitoring service."""
        if self.running:
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Server monitoring service started")
    
    async def stop(self):
        """Stop the monitoring service."""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Server monitoring service stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await self._check_all_servers()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Short delay on error
    
    async def _check_all_servers(self):
        """Check all servers."""
        logger.debug("Checking all servers...")
        
        with SessionLocal() as db:
            servers = db.query(Server).all()
            
            for server in servers:
                try:
                    await self._check_server(db, server)
                except Exception as e:
                    logger.error(f"Error checking server {server.name}: {e}")
            
            db.commit()
    
    async def _check_server(self, db: Session, server: Server):
        """Check a single server."""
        server_id = server.id
        
        try:
            # Prepare Glances connection details
            glances_host = server.glances_host or server.host
            glances_url = f"{server.glances_scheme}://{glances_host}:{server.glances_port}{server.glances_path}"
            
            # Prepare authentication
            auth = None
            headers = {}
            
            if server.glances_auth_type.value == "basic" and server.glances_username:
                username = server.glances_username
                password = server.glances_password or ""
                auth = (username, password)
            elif server.glances_auth_type.value == "token" and server.glances_token:
                token = server.glances_token or ""
                headers["Authorization"] = f"Bearer {token}"
            
            # Make quick health check request
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(glances_url, auth=auth, headers=headers)
                response.raise_for_status()
                data = response.json()
            
            if data:
                # Parse metrics for alert checking
                cpu_percent = self._get_cpu_percent(data)
                memory_percent = self._get_memory_percent(data)
                disk_percent = self._get_disk_percent(data)
                
                # Update server status
                server.status = ServerStatus.OK
                server.last_check_at = datetime.utcnow()
                server.failure_count = 0
                
                # Reset failure count
                self.server_failure_counts[server_id] = 0
                
                # Clear unreachable alert if it was set
                if self.server_alert_states['unreachable'].get(server_id, False):
                    await self._create_recovery_alert(db, server, "Server is now reachable")
                    self.server_alert_states['unreachable'][server_id] = False
                
                # Check for resource alerts  
                await self._check_resource_alerts(db, server, cpu_percent, memory_percent, disk_percent)
                
                logger.debug(f"Server {server.name} is healthy (CPU: {cpu_percent}%, Memory: {memory_percent}%, Disk: {disk_percent}%)")
            else:
                raise Exception("No data received from Glances API")
        
        except Exception as e:
            logger.warning(f"Server {server.name} check failed: {e}")
            
            # Increment failure count
            failure_count = self.server_failure_counts.get(server_id, 0) + 1
            self.server_failure_counts[server_id] = failure_count
            
            server.failure_count = failure_count
            server.last_check_at = datetime.utcnow()
            
            # Check if server should be marked as unreachable
            if failure_count >= 3:  # Mark unreachable after 3 failures
                if server.status != ServerStatus.UNREACHABLE:
                    server.status = ServerStatus.UNREACHABLE
                    await self._create_unreachable_alert(db, server, failure_count, str(e))
                    logger.error(f"Server {server.name} marked as unreachable after {failure_count} failures")
    
    def _get_cpu_percent(self, data: dict) -> float:
        """Extract CPU percentage from Glances data."""
        try:
            cpu_data = data.get('cpu', {})
            if isinstance(cpu_data, list) and len(cpu_data) > 0:
                if isinstance(cpu_data[0], dict):
                    return float(cpu_data[0].get('total', 0))
                return 0.0
            if isinstance(cpu_data, dict):
                return float(cpu_data.get('total', 0))
            return 0.0
        except (KeyError, ValueError, TypeError):
            return 0.0
    
    def _get_memory_percent(self, data: dict) -> float:
        """Extract memory percentage from Glances data."""
        try:
            mem_data = data.get('mem', {})
            return float(mem_data.get('percent', 0))
        except (KeyError, ValueError, TypeError):
            return 0.0
    
    def _get_disk_percent(self, data: dict) -> float:
        """Extract highest disk usage percentage from Glances data."""
        try:
            fs_data = data.get('fs', [])
            if not fs_data:
                return 0.0
            
            max_percent = 0.0
            for fs in fs_data:
                if isinstance(fs, dict):
                    percent = float(fs.get('percent', 0))
                    max_percent = max(max_percent, percent)
            return max_percent
        except (KeyError, ValueError, TypeError):
            return 0.0
    
    async def _check_resource_alerts(self, db: Session, server: Server, cpu_percent: float, memory_percent: float, disk_percent: float):
        """Check and create resource usage alerts."""
        server_id = server.id
        
        # CPU Alert
        if cpu_percent >= self.CPU_THRESHOLD:
            if not self.server_alert_states['cpu_high'].get(server_id, False):
                await self._create_resource_alert(db, server, "cpu", cpu_percent, self.CPU_THRESHOLD)
                self.server_alert_states['cpu_high'][server_id] = True
        else:
            if self.server_alert_states['cpu_high'].get(server_id, False):
                await self._create_recovery_alert(db, server, f"CPU usage normalized to {cpu_percent:.1f}%")
                self.server_alert_states['cpu_high'][server_id] = False
        
        # Memory Alert
        if memory_percent >= self.MEMORY_THRESHOLD:
            if not self.server_alert_states['memory_high'].get(server_id, False):
                await self._create_resource_alert(db, server, "memory", memory_percent, self.MEMORY_THRESHOLD)
                self.server_alert_states['memory_high'][server_id] = True
        else:
            if self.server_alert_states['memory_high'].get(server_id, False):
                await self._create_recovery_alert(db, server, f"Memory usage normalized to {memory_percent:.1f}%")
                self.server_alert_states['memory_high'][server_id] = False
        
        # Disk Alert
        if disk_percent >= self.DISK_THRESHOLD:
            if not self.server_alert_states['disk_high'].get(server_id, False):
                await self._create_resource_alert(db, server, "disk", disk_percent, self.DISK_THRESHOLD)
                self.server_alert_states['disk_high'][server_id] = True
        else:
            if self.server_alert_states['disk_high'].get(server_id, False):
                await self._create_recovery_alert(db, server, f"Disk usage normalized to {disk_percent:.1f}%")
                self.server_alert_states['disk_high'][server_id] = False
    
    async def _create_resource_alert(self, db: Session, server: Server, resource_type: str, current_value: float, threshold: float):
        """Create a resource usage alert."""
        emoji_map = {"cpu": "🔥", "memory": "📈", "disk": "💾"}
        emoji = emoji_map.get(resource_type, "⚠️")
        
        alert = Alert(
            level=AlertLevel.WARNING,
            title=f"{emoji} High {resource_type.upper()} usage on {server.name}",
            message=f"Server {server.name} ({server.host}) has high {resource_type} usage: {current_value:.1f}% (threshold: {threshold}%)",
            alert_type=f"{resource_type}_high",
            server_id=server.id
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        # Send Telegram notification
        telegram_sent = await self.telegram_client.send_alert(alert)
        if telegram_sent:
            alert.telegram_sent = True
            alert.telegram_sent_at = datetime.utcnow()
            db.commit()
            logger.info(f"Telegram notification sent for {resource_type} alert on {server.name}")
        else:
            logger.error(f"Failed to send Telegram notification for {resource_type} alert on {server.name}")
        
        logger.warning(f"High {resource_type} alert created for server {server.name}: {current_value:.1f}%")
    
    async def _create_recovery_alert(self, db: Session, server: Server, message: str):
        """Create a recovery alert."""
        alert = Alert(
            level=AlertLevel.INFO,
            title=f"✅ Server {server.name} recovered",
            message=f"Server {server.name} ({server.host}) has recovered: {message}",
            alert_type="server_recovered",
            server_id=server.id
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        # Send Telegram notification
        telegram_sent = await self.telegram_client.send_alert(alert)
        if telegram_sent:
            alert.telegram_sent = True
            alert.telegram_sent_at = datetime.utcnow()
            db.commit()
            logger.info(f"Telegram notification sent for recovery alert on {server.name}")
        else:
            logger.error(f"Failed to send Telegram notification for recovery alert on {server.name}")
        
        logger.info(f"Recovery alert created for server {server.name}: {message}")
    
    async def _create_unreachable_alert(self, db: Session, server: Server, failure_count: int, error: str):
        """Create an unreachable server alert."""
        if not self.server_alert_states['unreachable'].get(server.id, False):
            alert = Alert(
                level=AlertLevel.ERROR,
                title=f"🚨 Server {server.name} is unreachable",
                message=f"Server {server.name} ({server.host}) is unreachable after {failure_count} consecutive failures. Error: {error}",
                alert_type="server_unreachable",
                server_id=server.id
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            
            # Send Telegram notification
            telegram_sent = await self.telegram_client.send_alert(alert)
            if telegram_sent:
                alert.telegram_sent = True
                alert.telegram_sent_at = datetime.utcnow()
                db.commit()
                logger.info(f"Telegram notification sent for server {server.name}")
            else:
                logger.error(f"Failed to send Telegram notification for server {server.name}")
            
            self.server_alert_states['unreachable'][server.id] = True
            logger.error(f"Unreachable alert created for server {server.name}")


# Global monitor instance
monitor_service = ServerMonitorService()