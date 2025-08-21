"""
Domain management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import logging

from backend.database import get_db
from backend.models import Domain, DomainGroup, Server, Upstream, Task, TaskStatus, User
from backend.auth import get_admin_user, get_current_user_from_cookie
from backend.nginx_templates import NginxConfig, NginxDeployment
from backend.dns_utils import check_domain_ns
from backend.ssh_client import SSHClient
from backend.crypto import decrypt_if_needed

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ns-status")
async def get_ns_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get NS check status for all domains."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    domains = db.query(Domain).all()
    
    status_data = []
    for domain in domains:
        status_data.append({
            "id": domain.id,
            "domain": domain.domain,
            "last_ns_check_at": domain.last_ns_check_at.isoformat() if domain.last_ns_check_at else None,
            "ns_policy": domain.ns_policy
        })
    
    return {"domains": status_data}


class DomainCreate(BaseModel):
    domain: str
    server_id: int
    ssl: bool = False
    upstream_id: int
    group_id: Optional[int] = None
    ns_policy: str = "dnspod"
    notes: Optional[str] = None


class DomainUpdate(BaseModel):
    domain: Optional[str] = None
    server_id: Optional[int] = None
    ssl: Optional[bool] = None
    upstream_id: Optional[int] = None
    group_id: Optional[int] = None
    ns_policy: Optional[str] = None
    notes: Optional[str] = None


class DomainResponse(BaseModel):
    id: int
    domain: str
    server_id: int
    ssl: bool
    upstream_id: int
    group_id: Optional[int]
    ns_policy: str
    notes: Optional[str]
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


@router.get("/", response_model=List[DomainResponse])
async def list_domains(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    group_id: Optional[int] = None,
    server_id: Optional[int] = None,
    ssl: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List domains with optional filtering."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    query = db.query(Domain)
    
    if group_id is not None:
        query = query.filter(Domain.group_id == group_id)
    if server_id is not None:
        query = query.filter(Domain.server_id == server_id)
    if ssl is not None:
        query = query.filter(Domain.ssl == ssl)
    
    domains = query.offset(skip).limit(limit).all()
    return domains


@router.post("/", response_model=DomainResponse)
async def create_domain(
    request: Request,
    domain_data: DomainCreate,
    db: Session = Depends(get_db)
):
    """Create a new domain."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    # Check if domain already exists
    existing_domain = db.query(Domain).filter(Domain.domain == domain_data.domain).first()
    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain already exists"
        )
    
    # Validate server exists
    server = db.query(Server).filter(Server.id == domain_data.server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Validate upstream exists
    upstream = db.query(Upstream).filter(Upstream.id == domain_data.upstream_id).first()
    if not upstream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upstream not found"
        )
    
    # Validate group if provided
    if domain_data.group_id:
        group = db.query(DomainGroup).filter(DomainGroup.id == domain_data.group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain group not found"
            )
    
    # Create domain
    domain = Domain(
        domain=domain_data.domain,
        server_id=domain_data.server_id,
        ssl=domain_data.ssl,
        upstream_id=domain_data.upstream_id,
        group_id=domain_data.group_id,
        ns_policy=domain_data.ns_policy,
        notes=domain_data.notes
    )
    
    db.add(domain)
    db.commit()
    db.refresh(domain)
    
    logger.info(f"Domain {domain.domain} created by user {current_user.username}")
    return domain


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    request: Request,
    domain_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific domain."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    return domain


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    request: Request,
    domain_id: int,
    domain_data: DomainUpdate,
    db: Session = Depends(get_db)
):
    """Update a domain."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    # Validate references if provided
    if domain_data.server_id:
        server = db.query(Server).filter(Server.id == domain_data.server_id).first()
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
    
    if domain_data.upstream_id:
        upstream = db.query(Upstream).filter(Upstream.id == domain_data.upstream_id).first()
        if not upstream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upstream not found"
            )
    
    if domain_data.group_id:
        group = db.query(DomainGroup).filter(DomainGroup.id == domain_data.group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain group not found"
            )
    
    # Check for domain name conflicts
    if domain_data.domain and domain_data.domain != domain.domain:
        existing_domain = db.query(Domain).filter(Domain.domain == domain_data.domain).first()
        if existing_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain name already exists"
            )
    
    # Update fields
    update_data = domain_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(domain, field, value)
    
    db.commit()
    db.refresh(domain)
    
    logger.info(f"Domain {domain.domain} updated by user {current_user.username}")
    return domain


@router.delete("/{domain_id}")
async def delete_domain(
    request: Request,
    domain_id: int,
    db: Session = Depends(get_db)
):
    """Delete a domain."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    domain_name = domain.domain
    db.delete(domain)
    db.commit()
    
    logger.info(f"Domain {domain_name} deleted by user {current_user.username}")
    return {"message": "Domain deleted successfully"}


@router.post("/{domain_id}/deploy", response_model=TaskResponse)
async def deploy_domain(
    request: Request,
    domain_id: int,
    background_tasks: BackgroundTasks,
    email: str = "admin@example.com",
    db: Session = Depends(get_db)
):
    """Deploy domain configuration to server."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    # Create task
    task = Task(
        name=f"Deploy Domain - {domain.domain}",
        description=f"Deploying domain {domain.domain} to server",
        task_type="deploy_domain",
        domain_id=domain_id,
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Start background task
    background_tasks.add_task(run_deploy_domain_task, task.id, domain_id, email)
    
    return task


@router.post("/{domain_id}/verify-dns")
async def verify_domain_dns(
    request: Request,
    domain_id: int,
    db: Session = Depends(get_db)
):
    """Verify domain DNS configuration."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    server = db.query(Server).filter(Server.id == domain.server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    try:
        # Check NS policy only
        ns_servers, ns_valid, ns_error = await check_domain_ns(
            domain.domain, domain.ns_policy
        )
        
        return {
            "domain": domain.domain,
            "ns_policy": domain.ns_policy,
            "ns_check": {
                "valid": ns_valid,
                "servers": ns_servers,
                "error": ns_error
            }
        }
    
    except Exception as e:
        logger.error(f"Error verifying DNS for domain {domain.domain}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DNS verification failed: {str(e)}"
        )


@router.get("/{domain_id}/nginx-config")
async def get_nginx_config(
    request: Request,
    domain_id: int,
    db: Session = Depends(get_db)
):
    """Get Nginx configuration for a domain."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
        
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    upstream = db.query(Upstream).filter(Upstream.id == domain.upstream_id).first()
    if not upstream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upstream not found"
        )
    
    try:
        # Prepare upstream targets
        upstream_targets = [
            {
                "host": target.host,
                "port": target.port,
                "weight": target.weight
            }
            for target in upstream.targets
        ]
        
        # Generate configuration
        config = NginxConfig.generate_domain_config(
            domain.domain,
            upstream_targets,
            ssl=domain.ssl
        )
        
        return {
            "domain": domain.domain,
            "config": config,
            "file_path": NginxConfig.get_config_file_path(domain.domain)
        }
    
    except Exception as e:
        logger.error(f"Error generating Nginx config for domain {domain.domain}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration generation failed: {str(e)}"
        )


# Background task functions
async def run_deploy_domain_task(task_id: int, domain_id: int, email: str):
    """Run domain deployment task in background."""
    from backend.database import SessionLocal
    from backend.models import TaskLog
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        domain = db.query(Domain).filter(Domain.id == domain_id).first()
        
        if not task or not domain:
            return
        
        server = db.query(Server).filter(Server.id == domain.server_id).first()
        upstream = db.query(Upstream).filter(Upstream.id == domain.upstream_id).first()
        
        if not server or not upstream:
            task.status = TaskStatus.FAILED
            task.error_message = "Server or upstream not found"
            db.commit()
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
            message=f"Starting deployment of domain {domain.domain}"
        )
        db.add(log)
        db.commit()
        
        # Prepare upstream targets
        upstream_targets = [
            {
                "host": target.host,
                "port": target.port,
                "weight": target.weight
            }
            for target in upstream.targets
        ]
        
        # Generate Nginx configuration
        config = NginxConfig.generate_domain_config(
            domain.domain,
            upstream_targets,
            ssl=domain.ssl
        )
        
        task.progress = 20
        db.commit()
        
        # Connect to server
        password = decrypt_if_needed(server.password) if server.password else None
        ssh_key = decrypt_if_needed(server.ssh_key) if server.ssh_key else None
        ssh_key_passphrase = decrypt_if_needed(server.ssh_key_passphrase) if server.ssh_key_passphrase else None
        
        client = SSHClient(
            host=server.host,
            username=server.username,
            port=server.ssh_port,
            password=password,
            ssh_key=ssh_key,
            ssh_key_passphrase=ssh_key_passphrase
        )
        
        if not await client.connect():
            raise Exception("Failed to connect to server via SSH")
        
        task.progress = 30
        db.commit()
        
        # Check if Nginx is installed and install if needed
        log = TaskLog(
            task_id=task_id,
            level="INFO",
            source="nginx",
            message="Checking Nginx installation status"
        )
        db.add(log)
        db.commit()
        
        # Check if nginx is installed
        rc, stdout, stderr = await client.execute_command("which nginx")
        if rc != 0:
            # Nginx not found, install it
            log = TaskLog(
                task_id=task_id,
                level="INFO",
                source="nginx",
                message="Installing Nginx..."
            )
            db.add(log)
            db.commit()
            
            # Detect OS and install nginx
            rc, stdout, stderr = await client.execute_command("cat /etc/os-release")
            if rc == 0 and ("ubuntu" in stdout.lower() or "debian" in stdout.lower()):
                install_cmd = "apt update && apt install -y nginx"
            elif rc == 0 and ("centos" in stdout.lower() or "rhel" in stdout.lower() or "fedora" in stdout.lower()):
                install_cmd = "yum install -y nginx || dnf install -y nginx"
            else:
                install_cmd = "apt update && apt install -y nginx"  # Default to apt
            
            rc, stdout, stderr = await client.execute_command(install_cmd)
            if rc != 0:
                raise Exception(f"Failed to install Nginx: {stderr}")
            
            log = TaskLog(
                task_id=task_id,
                level="INFO",
                source="nginx",
                message="Nginx installed successfully"
            )
            db.add(log)
            db.commit()
        
        # Create sites-available and sites-enabled directories if they don't exist
        await client.execute_command("mkdir -p /etc/nginx/sites-available")
        await client.execute_command("mkdir -p /etc/nginx/sites-enabled")
        
        # Check if main nginx.conf includes sites-enabled
        rc, stdout, stderr = await client.execute_command("grep -q 'sites-enabled' /etc/nginx/nginx.conf")
        if rc != 0:
            # Add include directive for sites-enabled
            include_line = "    include /etc/nginx/sites-enabled/*;"
            await client.execute_command(f"sed -i '/http {{/a\\{include_line}' /etc/nginx/nginx.conf")
        
        task.progress = 45
        db.commit()
        
        # Upload configuration
        config_path = NginxConfig.get_config_file_path(domain.domain)
        if not await client.upload_file(config, config_path):
            raise Exception("Failed to upload Nginx configuration")
        
        task.progress = 60
        db.commit()
        
        # Enable site
        enable_cmd = NginxConfig.generate_enable_site_command(domain.domain)
        rc, stdout, stderr = await client.execute_command(enable_cmd)
        if rc != 0:
            raise Exception(f"Failed to enable site: {stderr}")
        
        task.progress = 70
        db.commit()
        
        # Test configuration
        test_cmd = NginxConfig.validate_config_command()
        rc, stdout, stderr = await client.execute_command(test_cmd)
        if rc != 0:
            raise Exception(f"Nginx configuration test failed: {stderr}")
        
        task.progress = 80
        db.commit()
        
        # SSL certificate if needed
        if domain.ssl:
            certbot_cmd = NginxConfig.generate_certbot_command(domain.domain, email)
            rc, stdout, stderr = await client.execute_command(certbot_cmd)
            if rc != 0:
                raise Exception(f"SSL certificate generation failed: {stderr}")
            
            task.progress = 90
            db.commit()
        
        # Reload Nginx
        reload_cmd = NginxConfig.reload_command()
        rc, stdout, stderr = await client.execute_command(reload_cmd)
        if rc != 0:
            raise Exception(f"Failed to reload Nginx: {stderr}")
        
        await client.disconnect()
        
        # Update task completion
        task.progress = 100
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = {"success": True, "domain": domain.domain}
        
        # Add completion log
        log = TaskLog(
            task_id=task_id,
            level="INFO",
            source="nginx",
            message=f"Domain {domain.domain} deployed successfully"
        )
        db.add(log)
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in domain deployment task: {e}")
        if 'task' in locals():
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
        
        log = TaskLog(
            task_id=task_id,
            level="ERROR",
            source="nginx",
            message=f"Domain deployment failed: {str(e)}"
        )
        db.add(log)
        db.commit()
    
    finally:
        db.close()


