"""
Server management API endpoints.
"""
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from backend.database import get_db
from backend.models import Server, AuthType, GlancesAuthType, ServerStatus, Task, TaskStatus, User
from backend.auth import get_admin_user, get_current_user_from_cookie
from backend.crypto import encrypt_if_needed, decrypt_if_needed
from backend.ssh_client import ServerProvisioner
from backend.glances_client import GlancesClient

logger = logging.getLogger(__name__)

router = APIRouter()


class ServerCreate(BaseModel):
    name: str
    host: str
    ssh_port: int = 22
    username: str
    auth_type: AuthType
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None
    glances_scheme: str = "http"
    glances_host: Optional[str] = None
    glances_port: int = 61208
    glances_path: str = "/api/4/all"
    glances_auth_type: GlancesAuthType = GlancesAuthType.NONE
    glances_username: Optional[str] = None
    glances_password: Optional[str] = None
    glances_token: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    ssh_port: Optional[int] = None
    username: Optional[str] = None
    auth_type: Optional[AuthType] = None
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None
    glances_scheme: Optional[str] = None
    glances_host: Optional[str] = None
    glances_port: Optional[int] = None
    glances_path: Optional[str] = None
    glances_auth_type: Optional[GlancesAuthType] = None
    glances_username: Optional[str] = None
    glances_password: Optional[str] = None
    glances_token: Optional[str] = None


class ServerResponse(BaseModel):
    id: int
    name: str
    host: str
    ssh_port: int
    username: str
    auth_type: AuthType
    glances_scheme: str
    glances_host: Optional[str]
    glances_port: int
    glances_path: str
    glances_auth_type: GlancesAuthType
    glances_username: Optional[str]
    status: ServerStatus
    failure_count: int
    last_check: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: int
    name: str
    status: TaskStatus
    progress: int
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[ServerResponse])
async def list_servers(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all servers."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    servers = db.query(Server).offset(skip).limit(limit).all()
    return servers


@router.get("/status")
async def get_servers_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get quick status of all servers."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    
    servers = db.query(Server).all()
    status_data = []
    
    for server in servers:
        status_data.append({
            "id": server.id,
            "name": server.name,
            "status": server.status.value,
            "last_check_at": server.last_check_at.isoformat() if server.last_check_at else None,
            "failure_count": server.failure_count
        })
    
    return {"servers": status_data}


@router.post("/", response_model=ServerResponse)
async def create_server(
    request: Request,
    server_data: ServerCreate,
    db: Session = Depends(get_db)
):
    """Create a new server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    # Check if server name already exists
    existing_server = db.query(Server).filter(Server.name == server_data.name).first()
    if existing_server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server with this name already exists"
        )
    
    # Encrypt sensitive data
    encrypted_password = encrypt_if_needed(server_data.password)
    encrypted_ssh_key = encrypt_if_needed(server_data.ssh_key)
    encrypted_ssh_key_passphrase = encrypt_if_needed(server_data.ssh_key_passphrase)
    encrypted_glances_password = encrypt_if_needed(server_data.glances_password)
    encrypted_glances_token = encrypt_if_needed(server_data.glances_token)
    
    # Create server
    server = Server(
        name=server_data.name,
        host=server_data.host,
        ssh_port=server_data.ssh_port,
        username=server_data.username,
        auth_type=server_data.auth_type,
        password=encrypted_password,
        ssh_key=encrypted_ssh_key,
        ssh_key_passphrase=encrypted_ssh_key_passphrase,
        glances_scheme=server_data.glances_scheme,
        glances_host=server_data.glances_host,
        glances_port=server_data.glances_port,
        glances_path=server_data.glances_path,
        glances_auth_type=server_data.glances_auth_type,
        glances_username=server_data.glances_username,
        glances_password=encrypted_glances_password,
        glances_token=encrypted_glances_token
    )
    
    db.add(server)
    db.commit()
    db.refresh(server)
    
    logger.info(f"Server {server.name} created by user {current_user.username}")
    return server


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    request: Request,
    server_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    return server


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    request: Request,
    server_id: int,
    server_data: ServerUpdate,
    db: Session = Depends(get_db)
):
    """Update a server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Update fields
    update_data = server_data.dict(exclude_unset=True)
    
    # Handle encrypted fields
    if "password" in update_data:
        update_data["password"] = encrypt_if_needed(update_data["password"])
    if "ssh_key" in update_data:
        update_data["ssh_key"] = encrypt_if_needed(update_data["ssh_key"])
    if "ssh_key_passphrase" in update_data:
        update_data["ssh_key_passphrase"] = encrypt_if_needed(update_data["ssh_key_passphrase"])
    if "glances_password" in update_data:
        update_data["glances_password"] = encrypt_if_needed(update_data["glances_password"])
    if "glances_token" in update_data:
        update_data["glances_token"] = encrypt_if_needed(update_data["glances_token"])
    
    for field, value in update_data.items():
        setattr(server, field, value)
    
    db.commit()
    db.refresh(server)
    
    logger.info(f"Server {server.name} updated by user {current_user.username}")
    return server


@router.delete("/{server_id}")
async def delete_server(
    request: Request,
    server_id: int,
    db: Session = Depends(get_db)
):
    """Delete a server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    server_name = server.name
    
    # Delete related records first to avoid foreign key constraint violations
    from backend.models import Task, Alert, TaskLog
    
    # Get tasks for this server to delete their logs first
    tasks = db.query(Task).filter(Task.server_id == server_id).all()
    task_ids = [task.id for task in tasks]
    
    # Delete task logs first (if any)
    if task_ids:
        db.query(TaskLog).filter(TaskLog.task_id.in_(task_ids)).delete(synchronize_session=False)
    
    # Delete related tasks
    db.query(Task).filter(Task.server_id == server_id).delete()
    
    # Delete related alerts
    db.query(Alert).filter(Alert.server_id == server_id).delete()
    
    # Now delete the server
    db.delete(server)
    db.commit()
    
    logger.info(f"Server {server_name} and related records deleted by user {current_user.username}")
    return {"message": "Server and related records deleted successfully"}


@router.post("/{server_id}/check-ssh", response_model=TaskResponse)
async def check_ssh_access(
    request: Request,
    server_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Check SSH access to a server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Create task
    task = Task(
        name=f"SSH Check - {server.name}",
        description=f"Checking SSH access to server {server.name}",
        task_type="ssh_check",
        server_id=server_id,
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Start background task
    background_tasks.add_task(run_ssh_check_task, task.id, server_id)
    
    return task


@router.post("/{server_id}/deploy-proxy", response_model=TaskResponse)
async def deploy_proxy(
    request: Request,
    server_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Deploy Nginx reverse proxy on a server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Create task
    task = Task(
        name=f"Deploy Proxy - {server.name}",
        description=f"Deploying Nginx reverse proxy on server {server.name}",
        task_type="deploy_proxy",
        server_id=server_id,
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Start background task
    background_tasks.add_task(run_deploy_proxy_task, task.id, server_id)
    
    return task


@router.post("/{server_id}/install-glances", response_model=TaskResponse)
async def install_glances(
    request: Request,
    server_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Install Glances monitoring on a server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Create task
    task = Task(
        name=f"Install Glances - {server.name}",
        description=f"Installing Glances monitoring on server {server.name}",
        task_type="install_glances",
        server_id=server_id,
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Start background task
    background_tasks.add_task(run_install_glances_task, task.id, server_id)
    
    return task


@router.post("/{server_id}/probe-glances")
async def probe_glances(
    server_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Probe Glances API on a server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    try:
        glances_client = GlancesClient()
        
        # Prepare connection details
        glances_host = server.glances_host or server.host
        glances_url = f"{server.glances_scheme}://{glances_host}:{server.glances_port}{server.glances_path}"
        
        # Prepare authentication
        auth = None
        headers = {}
        
        if server.glances_auth_type.value == "basic" and server.glances_username:
            username = server.glances_username
            password = decrypt_if_needed(server.glances_password) if server.glances_password else ""
            auth = (username, password)
        elif server.glances_auth_type.value == "token" and server.glances_token:
            token = decrypt_if_needed(server.glances_token)
            headers["Authorization"] = f"Bearer {token}"
        
        # Test connection
        success, message = await glances_client.test_connection(glances_url, auth, headers)
        
        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "message": message}
    
    except Exception as e:
        logger.error(f"Error probing Glances on server {server.name}: {e}")
        return {"success": False, "message": str(e)}


@router.get("/{server_id}/metrics")
async def get_server_metrics(
    server_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get recent metrics for a server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    metrics = (
        db.query(server.metrics)
        .order_by(server.metrics.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return {"server_id": server_id, "metrics": metrics}


# Background task functions
async def run_ssh_check_task(task_id: int, server_id: int):
    """Run SSH check task in background."""
    from backend.database import SessionLocal
    from backend.models import TaskLog
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        server = db.query(Server).filter(Server.id == server_id).first()
        
        if not task or not server:
            return
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.progress = 0
        db.commit()
        
        # Add log entry
        log = TaskLog(
            task_id=task_id,
            level="INFO",
            source="ssh",
            message=f"Starting SSH check for server {server.name}"
        )
        db.add(log)
        db.commit()
        
        # Perform SSH check
        success, message = await ServerProvisioner.check_ssh_access(server, task_id)
        
        # Update task progress
        task.progress = 100
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.result = {"success": success, "message": message}
        if not success:
            task.error_message = message
        
        # Add final log entry
        log = TaskLog(
            task_id=task_id,
            level="INFO" if success else "ERROR",
            source="ssh",
            message=f"SSH check completed: {message}"
        )
        db.add(log)
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in SSH check task: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        
        log = TaskLog(
            task_id=task_id,
            level="ERROR",
            source="ssh",
            message=f"SSH check failed: {str(e)}"
        )
        db.add(log)
        db.commit()
    
    finally:
        db.close()


async def run_deploy_proxy_task(task_id: int, server_id: int):
    """Run proxy deployment task in background."""
    from backend.database import SessionLocal
    from backend.models import TaskLog
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        server = db.query(Server).filter(Server.id == server_id).first()
        
        if not task or not server:
            return
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.progress = 0
        db.commit()
        
        # Add log entry
        log = TaskLog(
            task_id=task_id,
            level="INFO",
            source="nginx",
            message=f"Starting Nginx deployment on server {server.name}"
        )
        db.add(log)
        db.commit()
        
        # Deploy proxy
        success, logs = await ServerProvisioner.deploy_nginx_proxy(server)
        
        # Add log entries for each step
        for log_message in logs:
            log = TaskLog(
                task_id=task_id,
                level="INFO",
                source="nginx",
                message=log_message
            )
            db.add(log)
            task.progress = min(task.progress + 15, 95)
            db.commit()
        
        # Update task completion
        task.progress = 100
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.result = {"success": success, "logs": logs}
        if not success:
            task.error_message = "Nginx deployment failed"
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in proxy deployment task: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        db.commit()
    
    finally:
        db.close()


async def run_install_glances_task(task_id: int, server_id: int):
    """Run Glances installation task in background."""
    from backend.database import SessionLocal
    from backend.models import TaskLog
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        server = db.query(Server).filter(Server.id == server_id).first()
        
        if not task or not server:
            return
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.progress = 0
        db.commit()
        
        # Add log entry
        log = TaskLog(
            task_id=task_id,
            level="INFO",
            source="glances",
            message=f"Starting Glances installation on server {server.name}"
        )
        db.add(log)
        db.commit()
        
        # Install Glances
        success, logs = await ServerProvisioner.install_glances(server, server.glances_port)
        
        # Add log entries for each step
        for log_message in logs:
            log = TaskLog(
                task_id=task_id,
                level="INFO",
                source="glances",
                message=log_message
            )
            db.add(log)
            task.progress = min(task.progress + 12, 95)
            db.commit()
        
        # Update task completion
        task.progress = 100
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.result = {"success": success, "logs": logs}
        if not success:
            task.error_message = "Glances installation failed"
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in Glances installation task: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        db.commit()
    
    finally:
        db.close()
