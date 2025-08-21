"""
Background task scheduler using APScheduler.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import httpx
from typing import Dict, Any, Optional

from backend.config import settings
from backend.database import get_database_url
from backend.models import (
    Server, ServerMetric, Domain, NSCheck, Alert, Task, TaskLog,
    ServerStatus, AlertLevel, TaskStatus
)
from backend.glances_client import GlancesClient
from backend.telegram_client import TelegramClient
from backend.dns_utils import check_domain_ns
from backend.crypto import decrypt_if_needed

logger = logging.getLogger(__name__)

# Database setup for scheduler
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


class SchedulerService:
    """Background scheduler service."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.telegram_client = TelegramClient()
        self.glances_client = GlancesClient()
        self.server_failure_counts: Dict[int, int] = {}
    
    async def start(self):
        """Start the scheduler."""
        logger.info("Starting scheduler service...")
        
        # Schedule periodic tasks
        self.scheduler.add_job(
            self.poll_all_servers,
            IntervalTrigger(seconds=settings.GLANCES_POLL_INTERVAL),
            id="poll_servers",
            name="Poll Glances on all servers"
        )
        
        self.scheduler.add_job(
            self.check_domain_ns_all,
            IntervalTrigger(minutes=30),
            id="check_ns",
            name="Check NS records for all domains"
        )
        
        self.scheduler.add_job(
            self.cleanup_old_data,
            IntervalTrigger(hours=6),
            id="cleanup",
            name="Cleanup old metrics and logs"
        )
        
        self.scheduler.add_job(
            self.process_pending_alerts,
            IntervalTrigger(minutes=5),
            id="process_alerts",
            name="Process pending alerts"
        )
        
        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    async def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping scheduler service...")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    async def poll_all_servers(self):
        """Poll Glances API for all servers."""
        logger.debug("Starting server polling cycle")
        
        with SessionLocal() as db:
            servers = db.query(Server).all()
            
            for server in servers:
                try:
                    await self._poll_server(db, server)
                except Exception as e:
                    logger.error(f"Error polling server {server.name}: {e}", exc_info=True)
    
    async def _poll_server(self, db, server: Server):
        """Poll a single server."""
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
            
            # Make request to Glances API
            data = await self.glances_client.get_all_stats(
                url=glances_url,
                auth=auth,
                headers=headers,
                timeout=settings.GLANCES_TIMEOUT
            )
            
            if data:
                # Parse metrics
                metrics = self._parse_glances_data(data)
                
                # Save metrics to database
                metric = ServerMetric(
                    server_id=server_id,
                    cpu_percent=metrics.get("cpu_percent"),
                    memory_percent=metrics.get("memory_percent"),
                    disk_percent=metrics.get("disk_percent"),
                    load_1min=metrics.get("load_1min"),
                    load_5min=metrics.get("load_5min"),
                    load_15min=metrics.get("load_15min"),
                    uptime=metrics.get("uptime"),
                    raw_data=data
                )
                db.add(metric)
                
                # Update server status
                server.status = ServerStatus.OK
                server.last_check = datetime.utcnow()
                server.last_check_at = datetime.utcnow()
                server.failure_count = 0
                
                # Reset failure count
                self.server_failure_counts[server_id] = 0
                
                logger.debug(f"Successfully polled server {server.name}")
            else:
                raise Exception("No data received from Glances API")
        
        except Exception as e:
            logger.warning(f"Failed to poll server {server.name}: {e}")
            
            # Increment failure count
            failure_count = self.server_failure_counts.get(server_id, 0) + 1
            self.server_failure_counts[server_id] = failure_count
            
            server.failure_count = failure_count
            server.last_check = datetime.utcnow()
            server.last_check_at = datetime.utcnow()
            
            # Check if server should be marked as unreachable
            if failure_count >= settings.GLANCES_MAX_FAILURES:
                if server.status != ServerStatus.UNREACHABLE:
                    server.status = ServerStatus.UNREACHABLE
                    
                    # Create alert
                    alert = Alert(
                        level=AlertLevel.ERROR,
                        title=f"Server {server.name} is unreachable",
                        message=f"Server {server.name} ({server.host}) has been unreachable for {failure_count} consecutive checks. Last error: {str(e)}",
                        alert_type="server_unreachable",
                        server_id=server_id
                    )
                    db.add(alert)
                    logger.error(f"Server {server.name} marked as unreachable after {failure_count} failures")
        
        db.commit()
    
    def _parse_glances_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Glances API response data."""
        metrics = {}
        
        try:
            # CPU percentage
            if "cpu" in data and isinstance(data["cpu"], dict):
                cpu_total = data["cpu"].get("total", 0)
                metrics["cpu_percent"] = float(cpu_total) if cpu_total is not None else None
            
            # Memory percentage
            if "mem" in data and isinstance(data["mem"], dict):
                mem = data["mem"]
                if "total" in mem and "available" in mem and mem["total"] > 0:
                    used = mem["total"] - mem["available"]
                    metrics["memory_percent"] = (used / mem["total"]) * 100
            
            # Disk percentage (root filesystem)
            if "fs" in data and isinstance(data["fs"], list):
                for fs in data["fs"]:
                    if fs.get("mnt_point") == "/" and "percent" in fs:
                        metrics["disk_percent"] = float(fs["percent"])
                        break
            
            # Load average
            if "load" in data and isinstance(data["load"], dict):
                load = data["load"]
                metrics["load_1min"] = load.get("min1")
                metrics["load_5min"] = load.get("min5")
                metrics["load_15min"] = load.get("min15")
            
            # Uptime
            if "uptime" in data:
                metrics["uptime"] = int(data["uptime"]) if data["uptime"] is not None else None
        
        except Exception as e:
            logger.warning(f"Error parsing Glances data: {e}")
        
        return metrics
    
    async def check_domain_ns_all(self):
        """Check NS records for all domains."""
        logger.debug("Starting NS check cycle")
        
        with SessionLocal() as db:
            domains = db.query(Domain).all()
            
            for domain in domains:
                try:
                    await self._check_domain_ns(db, domain)
                except Exception as e:
                    logger.error(f"Error checking NS for domain {domain.domain}: {e}", exc_info=True)
    
    async def _check_domain_ns(self, db, domain: Domain):
        """Check NS records for a single domain."""
        try:
            ns_servers, is_valid, error = await check_domain_ns(
                domain.domain,
                domain.ns_policy,
                timeout=settings.DNS_TIMEOUT,
                dns_servers=settings.dns_servers_list
            )
            
            # Save NS check result
            ns_check = NSCheck(
                domain_id=domain.id,
                ns_servers=ns_servers,
                is_valid=is_valid,
                error_message=error
            )
            db.add(ns_check)
            
            # Create alert if NS check failed
            if not is_valid:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    title=f"NS check failed for {domain.domain}",
                    message=f"Domain {domain.domain} NS check failed. Policy: {domain.ns_policy}. NS servers: {', '.join(ns_servers) if ns_servers else 'None'}. Error: {error or 'Unknown'}",
                    alert_type="ns_check_failed",
                    domain_id=domain.id
                )
                db.add(alert)
                logger.warning(f"NS check failed for domain {domain.domain}: {error}")
            
            db.commit()
        
        except Exception as e:
            logger.error(f"Failed to check NS for domain {domain.domain}: {e}")
    
    async def cleanup_old_data(self):
        """Cleanup old metrics and logs."""
        logger.debug("Starting cleanup cycle")
        
        with SessionLocal() as db:
            try:
                # Delete metrics older than 30 days
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                
                deleted_metrics = db.query(ServerMetric).filter(
                    ServerMetric.created_at < cutoff_date
                ).delete()
                
                # Delete task logs older than 30 days
                deleted_logs = db.query(TaskLog).filter(
                    TaskLog.timestamp < cutoff_date
                ).delete()
                
                # Delete completed tasks older than 7 days
                task_cutoff = datetime.utcnow() - timedelta(days=7)
                deleted_tasks = db.query(Task).filter(
                    Task.status == TaskStatus.COMPLETED,
                    Task.completed_at < task_cutoff
                ).delete()
                
                db.commit()
                
                if deleted_metrics or deleted_logs or deleted_tasks:
                    logger.info(f"Cleanup completed: {deleted_metrics} metrics, {deleted_logs} logs, {deleted_tasks} tasks deleted")
            
            except Exception as e:
                logger.error(f"Error during cleanup: {e}", exc_info=True)
                db.rollback()
    
    async def process_pending_alerts(self):
        """Process and send pending alerts."""
        logger.debug("Processing pending alerts")
        
        with SessionLocal() as db:
            # Get unsent alerts
            alerts = db.query(Alert).filter(
                Alert.telegram_sent == False,
                Alert.is_resolved == False
            ).limit(10).all()
            
            for alert in alerts:
                try:
                    success = await self.telegram_client.send_alert(alert)
                    if success:
                        alert.telegram_sent = True
                        alert.telegram_sent_at = datetime.utcnow()
                        logger.info(f"Alert {alert.id} sent to Telegram")
                except Exception as e:
                    logger.error(f"Failed to send alert {alert.id} to Telegram: {e}")
            
            db.commit()


async def main():
    """Main scheduler entry point."""
    scheduler_service = SchedulerService()
    
    try:
        await scheduler_service.start()
        
        # Keep the scheduler running
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Scheduler error: {e}", exc_info=True)
    finally:
        await scheduler_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
