"""
Alert management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime
import logging

from backend.database import get_db
from backend.models import Alert, AlertLevel, User
from backend.auth import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter()


class AlertResponse(BaseModel):
    id: int
    level: AlertLevel
    title: str
    message: str
    alert_type: str
    server_id: Optional[int]
    domain_id: Optional[int]
    telegram_sent: bool
    telegram_sent_at: Optional[datetime]
    is_resolved: bool
    resolved_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertStats(BaseModel):
    total_alerts: int
    unresolved_alerts: int
    critical_alerts: int
    error_alerts: int
    warning_alerts: int
    info_alerts: int
    telegram_sent: int


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    skip: int = 0,
    limit: int = 100,
    level: Optional[AlertLevel] = None,
    alert_type: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    server_id: Optional[int] = None,
    domain_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """List alerts with optional filtering."""
    query = db.query(Alert)
    
    if level is not None:
        query = query.filter(Alert.level == level)
    if alert_type is not None:
        query = query.filter(Alert.alert_type == alert_type)
    if is_resolved is not None:
        query = query.filter(Alert.is_resolved == is_resolved)
    if server_id is not None:
        query = query.filter(Alert.server_id == server_id)
    if domain_id is not None:
        query = query.filter(Alert.domain_id == domain_id)
    
    alerts = (
        query
        .order_by(Alert.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return alerts


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    return alert


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Mark an alert as resolved."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    if alert.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already resolved"
        )
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Alert {alert_id} resolved by user {current_user.username}")
    return {"message": "Alert resolved successfully"}


@router.post("/{alert_id}/unresolve")
async def unresolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Mark an alert as unresolved."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    if not alert.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is not resolved"
        )
    
    alert.is_resolved = False
    alert.resolved_at = None
    db.commit()
    
    logger.info(f"Alert {alert_id} marked as unresolved by user {current_user.username}")
    return {"message": "Alert marked as unresolved"}


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    alert_title = alert.title
    db.delete(alert)
    db.commit()
    
    logger.info(f"Alert '{alert_title}' deleted by user {current_user.username}")
    return {"message": "Alert deleted successfully"}


@router.post("/bulk-resolve")
async def bulk_resolve_alerts(
    alert_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Resolve multiple alerts at once."""
    if not alert_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No alert IDs provided"
        )
    
    # Get alerts
    alerts = db.query(Alert).filter(
        Alert.id.in_(alert_ids),
        Alert.is_resolved == False
    ).all()
    
    if not alerts:
        return {"message": "No unresolved alerts found", "resolved_count": 0}
    
    # Mark as resolved
    resolved_count = 0
    for alert in alerts:
        alert.is_resolved = True
        alert.resolved_at = datetime.utcnow()
        resolved_count += 1
    
    db.commit()
    
    logger.info(f"Bulk resolved {resolved_count} alerts by user {current_user.username}")
    return {
        "message": f"Successfully resolved {resolved_count} alerts",
        "resolved_count": resolved_count
    }


@router.post("/bulk-delete")
async def bulk_delete_alerts(
    alert_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete multiple alerts at once."""
    if not alert_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No alert IDs provided"
        )
    
    # Count alerts to be deleted
    delete_count = db.query(Alert).filter(Alert.id.in_(alert_ids)).count()
    
    if delete_count == 0:
        return {"message": "No alerts found", "deleted_count": 0}
    
    # Delete alerts
    deleted_count = db.query(Alert).filter(Alert.id.in_(alert_ids)).delete()
    db.commit()
    
    logger.info(f"Bulk deleted {deleted_count} alerts by user {current_user.username}")
    return {
        "message": f"Successfully deleted {deleted_count} alerts",
        "deleted_count": deleted_count
    }


@router.get("/stats/overview", response_model=AlertStats)
async def get_alert_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get alert statistics overview."""
    total_alerts = db.query(func.count(Alert.id)).scalar()
    unresolved_alerts = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False).scalar()
    
    # Count by level
    critical_alerts = db.query(func.count(Alert.id)).filter(
        Alert.level == AlertLevel.CRITICAL,
        Alert.is_resolved == False
    ).scalar()
    
    error_alerts = db.query(func.count(Alert.id)).filter(
        Alert.level == AlertLevel.ERROR,
        Alert.is_resolved == False
    ).scalar()
    
    warning_alerts = db.query(func.count(Alert.id)).filter(
        Alert.level == AlertLevel.WARNING,
        Alert.is_resolved == False
    ).scalar()
    
    info_alerts = db.query(func.count(Alert.id)).filter(
        Alert.level == AlertLevel.INFO,
        Alert.is_resolved == False
    ).scalar()
    
    telegram_sent = db.query(func.count(Alert.id)).filter(Alert.telegram_sent == True).scalar()
    
    return AlertStats(
        total_alerts=total_alerts or 0,
        unresolved_alerts=unresolved_alerts or 0,
        critical_alerts=critical_alerts or 0,
        error_alerts=error_alerts or 0,
        warning_alerts=warning_alerts or 0,
        info_alerts=info_alerts or 0,
        telegram_sent=telegram_sent or 0
    )


@router.get("/types/list")
async def get_alert_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get list of all alert types in the system."""
    alert_types = (
        db.query(Alert.alert_type, func.count(Alert.id))
        .group_by(Alert.alert_type)
        .order_by(func.count(Alert.id).desc())
        .all()
    )
    
    return {
        "alert_types": [
            {"type": alert_type, "count": count}
            for alert_type, count in alert_types
        ]
    }


@router.post("/cleanup")
async def cleanup_old_alerts(
    days: int = 90,
    resolved_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Clean up old alerts."""
    from datetime import timedelta
    
    if days < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be at least 1"
        )
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Build query
    query = db.query(Alert).filter(Alert.created_at < cutoff_date)
    if resolved_only:
        query = query.filter(Alert.is_resolved == True)
    
    # Count alerts to be deleted
    alert_count = query.count()
    
    if alert_count == 0:
        return {"message": "No alerts to clean up", "deleted_count": 0}
    
    # Delete alerts
    deleted_count = query.delete()
    db.commit()
    
    logger.info(f"Cleaned up {deleted_count} old alerts by user {current_user.username}")
    
    return {
        "message": f"Successfully cleaned up {deleted_count} alerts older than {days} days",
        "deleted_count": deleted_count
    }


@router.get("/recent/unresolved")
async def get_recent_unresolved_alerts(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get recent unresolved alerts for dashboard."""
    alerts = (
        db.query(Alert)
        .filter(Alert.is_resolved == False)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return {"alerts": alerts}
