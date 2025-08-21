"""
NS monitoring service with background checks.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

from backend.config import settings
from backend.database import get_database_url
from backend.models import Domain, NSCheck, Alert, AlertLevel
from backend.dns_utils import check_domain_ns
from backend.telegram_client import TelegramClient, mask_domain

logger = logging.getLogger(__name__)

# Database setup for monitor
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


class NSMonitorService:
    """Background NS monitoring service."""
    
    def __init__(self):
        self.telegram_client = TelegramClient()
        self.domain_alert_states: Dict[int, bool] = {}  # Track which domains have active NS alerts
        self.running = False
        self.monitor_task = None
    
    async def start(self):
        """Start the monitoring service."""
        if self.running:
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("NS monitoring service started")
        
        # Run initial check immediately
        try:
            await self._check_all_domains()
            logger.info("Initial NS check completed")
        except Exception as e:
            logger.error(f"Initial NS check failed: {e}")
    
    async def stop(self):
        """Stop the monitoring service."""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("NS monitoring service stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                logger.info("Starting NS check cycle...")
                await self._check_all_domains()
                logger.info("NS check cycle completed")
                await asyncio.sleep(60)  # Check every 1 minute for testing, then change to 300
            except asyncio.CancelledError:
                logger.info("NS monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in NS monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Short delay on error
    
    async def _check_all_domains(self):
        """Check NS records for all domains."""
        logger.info("Checking NS records for all domains...")
        
        with SessionLocal() as db:
            domains = db.query(Domain).all()
            logger.info(f"Found {len(domains)} domains to check")
            
            for domain in domains:
                try:
                    logger.info(f"Checking NS for domain: {domain.domain}")
                    await self._check_domain_ns(db, domain)
                    logger.info(f"NS check completed for domain: {domain.domain}")
                except Exception as e:
                    logger.error(f"Error checking NS for domain {domain.domain}: {e}")
                    
            db.commit()
            logger.info("All NS checks completed and committed to database")
    
    async def _check_domain_ns(self, db: Session, domain: Domain):
        """Check NS records for a single domain."""
        try:
            # Perform NS check
            ns_servers, is_valid, error = await check_domain_ns(domain.domain, domain.ns_policy)
            
            # Create NS check record
            ns_check = NSCheck(
                domain_id=domain.id,
                ns_servers=ns_servers,
                is_valid=is_valid,
                error_message=error,
                checked_at=datetime.utcnow()
            )
            
            db.add(ns_check)
            
            # Update domain's last check time
            domain.last_ns_check_at = datetime.utcnow()
            
            # Check for NS alerts
            await self._check_ns_alerts(db, domain, is_valid, ns_servers, error)
            
            logger.debug(f"NS check completed for {domain.domain}: {is_valid}")
            
        except Exception as e:
            logger.error(f"Failed to check NS for {domain.domain}: {e}")
            
            # Still record the failed check
            ns_check = NSCheck(
                domain_id=domain.id,
                ns_servers=[],
                is_valid=False,
                error_message=str(e),
                checked_at=datetime.utcnow()
            )
            
            db.add(ns_check)
            domain.last_ns_check_at = datetime.utcnow()
            
            # Check for NS alerts
            await self._check_ns_alerts(db, domain, False, [], str(e) if e else "")
    
    async def _check_ns_alerts(self, db: Session, domain: Domain, is_valid: bool, ns_servers: List[str], error: str):
        """Check and create NS alerts for a domain."""
        domain_id = domain.id
        
        if not is_valid:
            # NS check failed - create alert if not already active
            if not self.domain_alert_states.get(domain_id, False):
                await self._create_ns_failed_alert(db, domain, ns_servers, error)
                self.domain_alert_states[domain_id] = True
        else:
            # NS check passed - clear alert if was active
            if self.domain_alert_states.get(domain_id, False):
                await self._create_ns_recovery_alert(db, domain, ns_servers)
                self.domain_alert_states[domain_id] = False
    
    async def _create_ns_failed_alert(self, db: Session, domain: Domain, ns_servers: List[str], error: str):
        """Create a NS check failed alert."""
        ns_info = f"NS servers: {', '.join(ns_servers)}" if ns_servers else "No NS servers found"
        
        masked_domain = mask_domain(domain.domain)
        alert = Alert(
            level=AlertLevel.WARNING,
            title=f"🔍 NS check failed for {masked_domain}",
            message=f"Domain {masked_domain} failed NS policy check '{domain.ns_policy}'. {ns_info}. Error: {error or 'Policy mismatch'}",
            alert_type="ns_check_failed",
            domain_id=domain.id
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
            logger.info(f"Telegram notification sent for NS failed alert on {domain.domain}")
        else:
            logger.error(f"Failed to send Telegram notification for NS failed alert on {domain.domain}")
        
        logger.warning(f"NS failed alert created for domain {domain.domain}")
    
    async def _create_ns_recovery_alert(self, db: Session, domain: Domain, ns_servers: List[str]):
        """Create a NS recovery alert."""
        ns_info = f"NS servers: {', '.join(ns_servers)}" if ns_servers else "NS resolved"
        
        masked_domain = mask_domain(domain.domain)
        alert = Alert(
            level=AlertLevel.INFO,
            title=f"✅ NS recovered for {masked_domain}",
            message=f"Domain {masked_domain} NS policy '{domain.ns_policy}' is now valid. {ns_info}",
            alert_type="ns_recovered",
            domain_id=domain.id
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
            logger.info(f"Telegram notification sent for NS recovery alert on {domain.domain}")
        else:
            logger.error(f"Failed to send Telegram notification for NS recovery alert on {domain.domain}")
        
        logger.info(f"NS recovery alert created for domain {domain.domain}")
    
    async def _create_ns_error_alert(self, db: Session, domain: Domain, error: str):
        """Create a NS check error alert."""
        masked_domain = mask_domain(domain.domain)
        alert = Alert(
            level=AlertLevel.ERROR,
            title=f"❌ NS check error for {masked_domain}",
            message=f"Failed to check NS records for domain {masked_domain}. Error: {error}",
            alert_type="ns_check_error",
            domain_id=domain.id
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
            logger.info(f"Telegram notification sent for NS error alert on {domain.domain}")
        else:
            logger.error(f"Failed to send Telegram notification for NS error alert on {domain.domain}")
        
        logger.error(f"NS error alert created for domain {domain.domain}")


# Global monitor instance
ns_monitor = NSMonitorService()