"""
UI routes for server-side rendering with Jinja2.
"""
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
import sqlalchemy
from typing import Optional
import logging

from backend.database import get_db
from backend.models import (
    Server, Upstream, Domain, DomainGroup, Task, Alert, User,
    ServerStatus, TaskStatus, AlertLevel
)
from backend.auth import get_current_active_user, authenticate_user, create_access_token
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session, return None if not authenticated."""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        from backend.auth import verify_token
        username = verify_token(token)
        if not username:
            return None
        
        user = db.query(User).filter(User.username == username).first()
        return user if user and user.is_active else None
    except:
        return None


@router.get("/api/ui/dashboard/stream")
async def dashboard_stream(
    request: Request,
    db: Session = Depends(get_db)
):
    """Server-sent events endpoint for real-time dashboard updates."""
    # Get user from cookie but don't require authentication for dashboard stream
    current_user = get_current_user_optional(request, db)
    if not current_user:
        # Return empty data for non-authenticated users instead of 401
        from fastapi.responses import StreamingResponse
        import json
        import asyncio
        
        async def empty_stream():
            while True:
                yield f"data: {json.dumps({})}\n\n"
                await asyncio.sleep(5)
        
        return StreamingResponse(empty_stream(), media_type="text/plain")
    
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    
    async def event_stream():
        while True:
            try:
                # Gather current statistics
                total_servers = db.query(func.count(Server.id)).scalar() or 0
                online_servers = db.query(func.count(Server.id)).filter(Server.status == ServerStatus.OK).scalar() or 0
                total_domains = db.query(func.count(Domain.id)).scalar() or 0
                ssl_domains = db.query(func.count(Domain.id)).filter(Domain.ssl == True).scalar() or 0
                unresolved_alerts = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False).scalar() or 0
                
                stats = {
                    "total_servers": total_servers,
                    "online_servers": online_servers,
                    "total_domains": total_domains,
                    "ssl_domains": ssl_domains,
                    "unresolved_alerts": unresolved_alerts
                }
                
                yield f"data: {json.dumps(stats)}\n\n"
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Dashboard stream error: {e}")
                break
    
    return StreamingResponse(event_stream(), media_type="text/plain")


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Main dashboard page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # Gather dashboard statistics
    total_servers = db.query(func.count(Server.id)).scalar() or 0
    online_servers = db.query(func.count(Server.id)).filter(Server.status == ServerStatus.OK).scalar() or 0
    
    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    ssl_domains = db.query(func.count(Domain.id)).filter(Domain.ssl == True).scalar() or 0
    
    unresolved_alerts = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False).scalar() or 0
    
    # Recent tasks
    recent_tasks = (
        db.query(Task)
        .order_by(Task.created_at.desc())
        .limit(5)
        .all()
    )
    
    # Recent alerts
    recent_alerts = (
        db.query(Alert)
        .filter(Alert.is_resolved == False)
        .order_by(Alert.created_at.desc())
        .limit(5)
        .all()
    )
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": current_user,
        "stats": {
            "total_servers": total_servers,
            "online_servers": online_servers,
            "total_domains": total_domains,
            "ssl_domains": ssl_domains,
            "unresolved_alerts": unresolved_alerts
        },
        "recent_tasks": recent_tasks,
        "recent_alerts": recent_alerts
    })


@router.get("/api/ui/dashboard/stats")
async def dashboard_stats_api(
    request: Request,
    db: Session = Depends(get_db)
):
    """API endpoint for dashboard statistics."""
    # Get user from cookie but don't require authentication for dashboard stats
    current_user = get_current_user_optional(request, db)
    if not current_user:
        # Return empty stats for non-authenticated users
        return {
            "total_servers": 0,
            "online_servers": 0,
            "total_domains": 0,
            "ssl_domains": 0,
            "unresolved_alerts": 0
        }
    
    # Gather dashboard statistics
    total_servers = db.query(func.count(Server.id)).scalar() or 0
    online_servers = db.query(func.count(Server.id)).filter(Server.status == ServerStatus.OK).scalar() or 0
    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    ssl_domains = db.query(func.count(Domain.id)).filter(Domain.ssl == True).scalar() or 0
    unresolved_alerts = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False).scalar() or 0
    
    return {
        "total_servers": total_servers,
        "online_servers": online_servers,
        "total_domains": total_domains,
        "ssl_domains": ssl_domains,
        "unresolved_alerts": unresolved_alerts
    }


@router.get("/servers", response_class=HTMLResponse)
async def servers_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Servers management page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
        
    servers = db.query(Server).order_by(Server.name).all()
    
    return templates.TemplateResponse("servers.html", {
        "request": request,
        "current_user": current_user,
        "servers": servers
    })


@router.get("/servers/{server_id}/monitor", response_class=HTMLResponse)
async def server_monitor_page(
    server_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Individual server monitoring page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    return templates.TemplateResponse("server_monitor.html", {
        "request": request,
        "current_user": current_user,
        "server": server
    })


@router.get("/api/servers/{server_id}/glances-data")
async def get_server_glances_data(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get real-time Glances data for a specific server."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Build Glances URL
    glances_url = f"{server.glances_scheme}://{server.glances_host or server.host}:{server.glances_port}{server.glances_path}"
    
    # Get authentication if configured
    auth = None
    from backend.models import GlancesAuthType
    if server.glances_auth_type == GlancesAuthType.BASIC and server.glances_username:
        # For now, just use the password as-is (encryption can be added later)
        # from backend.encryption import decrypt_if_needed
        password = server.glances_password if server.glances_password else ""
        auth = (server.glances_username, password)
    
    # Fetch data from Glances
    from backend.glances_client import GlancesClient
    client = GlancesClient()
    data = await client.get_all_stats(glances_url, auth)
    
    if data:
        return {"success": True, "data": data}
    else:
        return {"success": False, "error": "Failed to fetch Glances data"}


@router.get("/upstreams", response_class=HTMLResponse)
async def upstreams_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Upstreams management page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
        
    upstreams = db.query(Upstream).order_by(Upstream.name).all()
    
    return templates.TemplateResponse("upstreams.html", {
        "request": request,
        "current_user": current_user,
        "upstreams": upstreams
    })


@router.get("/domains", response_class=HTMLResponse)
async def domains_page(
    request: Request,
    group_id: Optional[int] = None,
    server_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Domains management page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
        
    query = db.query(Domain)
    
    if group_id:
        query = query.filter(Domain.group_id == group_id)
    if server_id:
        query = query.filter(Domain.server_id == server_id)
    
    domains = query.order_by(Domain.domain).all()
    
    # Get related data for filters and forms
    groups = db.query(DomainGroup).order_by(DomainGroup.name).all()
    servers = db.query(Server).order_by(Server.name).all()
    upstreams = db.query(Upstream).order_by(Upstream.name).all()
    
    return templates.TemplateResponse("domains.html", {
        "request": request,
        "current_user": current_user,
        "domains": domains,
        "groups": groups,
        "servers": servers,
        "upstreams": upstreams,
        "selected_group_id": group_id,
        "selected_server_id": server_id
    })


@router.get("/groups", response_class=HTMLResponse)
async def groups_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Domain groups management page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
        
    # Query groups with domain counts
    groups_query = (
        db.query(
            DomainGroup,
            func.count(Domain.id).label('domain_count'),
            func.sum(func.cast(Domain.ssl, sqlalchemy.Integer)).label('ssl_count')
        )
        .outerjoin(Domain)
        .group_by(DomainGroup.id)
        .order_by(DomainGroup.name)
    )
    
    groups_data = []
    for group, domain_count, ssl_count in groups_query.all():
        groups_data.append({
            "group": group,
            "domain_count": domain_count or 0,
            "ssl_count": ssl_count or 0
        })
    
    return templates.TemplateResponse("groups.html", {
        "request": request,
        "current_user": current_user,
        "groups_data": groups_data
    })


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Logs and tasks page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
        
    query = db.query(Task)
    
    if task_type:
        query = query.filter(Task.task_type == task_type)
    if status:
        try:
            task_status = TaskStatus(status)
            query = query.filter(Task.status == task_status)
        except ValueError:
            pass  # Invalid status, ignore filter
    
    tasks = query.order_by(Task.created_at.desc()).limit(50).all()
    
    # Get unique task types for filter
    task_types = (
        db.query(Task.task_type)
        .distinct()
        .order_by(Task.task_type)
        .all()
    )
    task_types = [t[0] for t in task_types]
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "current_user": current_user,
        "tasks": tasks,
        "task_types": task_types,
        "selected_task_type": task_type,
        "selected_status": status,
        "task_statuses": [s.value for s in TaskStatus]
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Settings management page."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
        
    from backend.models import Setting
    from backend.crypto import decrypt_if_needed
    
    # Get all settings
    settings_data = db.query(Setting).order_by(Setting.key).all()
    
    # Group settings by category
    categorized_settings = {
        "telegram": [],
        "glances": [],
        "dns": [],
        "ssh": [],
        "alerts": [],
        "tasks": [],
        "metrics": [],
        "other": []
    }
    
    for setting in settings_data:
        # Determine category from key
        if setting.key.startswith("telegram."):
            category = "telegram"
        elif setting.key.startswith("glances."):
            category = "glances"
        elif setting.key.startswith("dns."):
            category = "dns"
        elif setting.key.startswith("ssh."):
            category = "ssh"
        elif setting.key.startswith("alerts."):
            category = "alerts"
        elif setting.key.startswith("tasks."):
            category = "tasks"
        elif setting.key.startswith("metrics."):
            category = "metrics"
        else:
            category = "other"
        
        # Mask encrypted values
        if setting.is_encrypted and setting.value:
            decrypted_value = decrypt_if_needed(setting.value.encode() if isinstance(setting.value, str) else setting.value)
            display_value = "*" * min(len(decrypted_value), 8) if decrypted_value else ""
        else:
            display_value = decrypt_if_needed(setting.value.encode() if isinstance(setting.value, str) else setting.value) if setting.value else ""
        
        categorized_settings[category].append({
            "setting": setting,
            "display_value": display_value
        })
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_user": current_user,
        "categorized_settings": categorized_settings
    })


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("auth/login.html", {
        "request": request
    })


@router.post("/auth/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form submission."""
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid username or password"
        }, status_code=400)
    
    # Create access token
    from datetime import timedelta
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Redirect to dashboard with token cookie
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEBUG
    )
    
    logger.info(f"User {user.username} logged in via web interface")
    return response


@router.get("/auth/logout")
async def logout():
    """Handle logout."""
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# AJAX endpoints for dynamic content
@router.get("/api/ui/server-metrics/{server_id}")
async def get_server_metrics_ui(
    server_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get server metrics for UI charts."""
    from backend.models import ServerMetric
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    metrics = (
        db.query(ServerMetric)
        .filter(ServerMetric.server_id == server_id)
        .order_by(ServerMetric.created_at.desc())
        .limit(limit)
        .all()
    )
    
    # Reverse to get chronological order
    metrics = list(reversed(metrics))
    
    return {
        "server_name": server.name,
        "metrics": [
            {
                "timestamp": metric.created_at.isoformat(),
                "cpu_percent": metric.cpu_percent,
                "memory_percent": metric.memory_percent,
                "disk_percent": metric.disk_percent,
                "load_1min": metric.load_1min,
                "uptime": metric.uptime
            }
            for metric in metrics
        ]
    }


@router.get("/api/ui/alerts/recent")
async def get_recent_alerts_ui(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get recent alerts for UI notifications."""
    alerts = (
        db.query(Alert)
        .filter(Alert.is_resolved == False)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return {
        "alerts": [
            {
                "id": alert.id,
                "level": alert.level.value,
                "title": alert.title,
                "message": alert.message,
                "created_at": alert.created_at.isoformat(),
                "alert_type": alert.alert_type
            }
            for alert in alerts
        ]
    }


@router.get("/api/ui/tasks/running")
async def get_running_tasks_ui(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get running tasks for UI progress tracking."""
    tasks = (
        db.query(Task)
        .filter(Task.status == TaskStatus.RUNNING)
        .order_by(Task.started_at.desc())
        .all()
    )
    
    return {
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "progress": task.progress,
                "task_type": task.task_type,
                "started_at": task.started_at.isoformat() if task.started_at else None
            }
            for task in tasks
        ]
    }


@router.get("/api/ui/dashboard/stats")
async def get_dashboard_stats_ui(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get dashboard statistics for real-time updates."""
    stats = {
        "servers": {
            "total": db.query(func.count(Server.id)).scalar() or 0,
            "online": db.query(func.count(Server.id)).filter(Server.status == ServerStatus.OK).scalar() or 0,
            "unreachable": db.query(func.count(Server.id)).filter(Server.status == ServerStatus.UNREACHABLE).scalar() or 0
        },
        "domains": {
            "total": db.query(func.count(Domain.id)).scalar() or 0,
            "ssl": db.query(func.count(Domain.id)).filter(Domain.ssl == True).scalar() or 0
        },
        "alerts": {
            "unresolved": db.query(func.count(Alert.id)).filter(Alert.is_resolved == False).scalar() or 0,
            "critical": db.query(func.count(Alert.id)).filter(
                Alert.is_resolved == False,
                Alert.level == AlertLevel.CRITICAL
            ).scalar() or 0
        },
        "tasks": {
            "running": db.query(func.count(Task.id)).filter(Task.status == TaskStatus.RUNNING).scalar() or 0,
            "pending": db.query(func.count(Task.id)).filter(Task.status == TaskStatus.PENDING).scalar() or 0
        }
    }
    
    return stats
