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
from backend.models import Server, ServerStatus
from backend.glances_client import GlancesClient

logger = logging.getLogger(__name__)

# Database setup for monitor
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


class ServerMonitorService:
    """Background server monitoring service."""
    
    def __init__(self):
        self.glances_client = GlancesClient()
        self.server_failure_counts: Dict[int, int] = {}
        self.running = False
        self.monitor_task = None
    
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
                # Update server status
                server.status = ServerStatus.OK
                server.last_check_at = datetime.utcnow()
                server.failure_count = 0
                
                # Reset failure count
                self.server_failure_counts[server_id] = 0
                
                logger.debug(f"Server {server.name} is healthy")
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
                    logger.error(f"Server {server.name} marked as unreachable after {failure_count} failures")


# Global monitor instance
monitor_service = ServerMonitorService()