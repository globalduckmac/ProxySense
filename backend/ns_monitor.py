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
from backend.models import Domain, NSCheck
from backend.dns_utils import check_domain_ns

logger = logging.getLogger(__name__)

# Database setup for monitor
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


class NSMonitorService:
    """Background NS monitoring service."""
    
    def __init__(self):
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


# Global monitor instance
ns_monitor = NSMonitorService()