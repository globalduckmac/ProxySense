"""
Domain group management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from pydantic import BaseModel
from datetime import datetime
import logging

from backend.database import get_db
from backend.models import DomainGroup, Domain, User
from backend.auth import get_admin_user, get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter()


class DomainGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DomainGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DomainGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    domain_count: int = 0
    ssl_count: int = 0
    
    class Config:
        from_attributes = True


class DomainGroupStats(BaseModel):
    total_groups: int
    total_domains: int
    ssl_domains: int
    non_ssl_domains: int


@router.get("/", response_model=List[DomainGroupResponse])
async def list_domain_groups(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all domain groups with statistics."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    
    # Query groups with domain counts
    groups_query = (
        db.query(
            DomainGroup,
            func.count(Domain.id).label('domain_count'),
            func.sum(func.cast(Domain.ssl, Integer)).label('ssl_count')
        )
        .outerjoin(Domain)
        .group_by(DomainGroup.id)
        .offset(skip)
        .limit(limit)
    )
    
    results = groups_query.all()
    
    # Convert to response objects
    groups = []
    for group, domain_count, ssl_count in results:
        group_response = DomainGroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            domain_count=domain_count or 0,
            ssl_count=ssl_count or 0
        )
        groups.append(group_response)
    
    return groups


@router.post("/", response_model=DomainGroupResponse)
async def create_domain_group(
    request: Request,
    group_data: DomainGroupCreate,
    db: Session = Depends(get_db)
):
    """Create a new domain group."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    
    # Check if group name already exists
    existing_group = db.query(DomainGroup).filter(DomainGroup.name == group_data.name).first()
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain group with this name already exists"
        )
    
    # Create group
    group = DomainGroup(
        name=group_data.name,
        description=group_data.description
    )
    
    db.add(group)
    db.commit()
    db.refresh(group)
    
    logger.info(f"Domain group {group.name} created by user {current_user.username}")
    
    # Return with statistics
    return DomainGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        domain_count=0,
        ssl_count=0
    )


@router.get("/{group_id}", response_model=DomainGroupResponse)
async def get_domain_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific domain group with statistics."""
    group = db.query(DomainGroup).filter(DomainGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain group not found"
        )
    
    # Get statistics
    domain_count = db.query(func.count(Domain.id)).filter(Domain.group_id == group_id).scalar()
    ssl_count = db.query(func.count(Domain.id)).filter(
        Domain.group_id == group_id,
        Domain.ssl == True
    ).scalar()
    
    return DomainGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        domain_count=domain_count or 0,
        ssl_count=ssl_count or 0
    )


@router.put("/{group_id}", response_model=DomainGroupResponse)
async def update_domain_group(
    group_id: int,
    group_data: DomainGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update a domain group."""
    group = db.query(DomainGroup).filter(DomainGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain group not found"
        )
    
    # Check for name conflicts
    if group_data.name and group_data.name != group.name:
        existing_group = db.query(DomainGroup).filter(DomainGroup.name == group_data.name).first()
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain group with this name already exists"
            )
    
    # Update fields
    update_data = group_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)
    
    db.commit()
    db.refresh(group)
    
    logger.info(f"Domain group {group.name} updated by user {current_user.username}")
    
    # Get updated statistics
    domain_count = db.query(func.count(Domain.id)).filter(Domain.group_id == group_id).scalar()
    ssl_count = db.query(func.count(Domain.id)).filter(
        Domain.group_id == group_id,
        Domain.ssl == True
    ).scalar()
    
    return DomainGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        domain_count=domain_count or 0,
        ssl_count=ssl_count or 0
    )


@router.delete("/{group_id}")
async def delete_domain_group(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a domain group."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    
    group = db.query(DomainGroup).filter(DomainGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain group not found"
        )
    
    # Check if group has domains
    domain_count = db.query(func.count(Domain.id)).filter(Domain.group_id == group_id).scalar()
    if domain_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete group with {domain_count} domains. Move or delete domains first."
        )
    
    group_name = group.name
    db.delete(group)
    db.commit()
    
    logger.info(f"Domain group {group_name} deleted by user {current_user.username}")
    return {"message": "Domain group deleted successfully"}


@router.get("/{group_id}/domains")
async def get_group_domains(
    group_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get all domains in a specific group."""
    group = db.query(DomainGroup).filter(DomainGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain group not found"
        )
    
    domains = (
        db.query(Domain)
        .filter(Domain.group_id == group_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return {
        "group_id": group_id,
        "group_name": group.name,
        "domains": domains
    }


@router.get("/stats/overview", response_model=DomainGroupStats)
async def get_domain_group_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get overall domain group statistics."""
    total_groups = db.query(func.count(DomainGroup.id)).scalar()
    total_domains = db.query(func.count(Domain.id)).scalar()
    ssl_domains = db.query(func.count(Domain.id)).filter(Domain.ssl == True).scalar()
    
    return DomainGroupStats(
        total_groups=total_groups or 0,
        total_domains=total_domains or 0,
        ssl_domains=ssl_domains or 0,
        non_ssl_domains=(total_domains or 0) - (ssl_domains or 0)
    )


@router.post("/{group_id}/move-domains")
async def move_domains_to_group(
    group_id: int,
    domain_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Move multiple domains to a group."""
    # Validate group exists
    group = db.query(DomainGroup).filter(DomainGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain group not found"
        )
    
    # Validate all domains exist
    domains = db.query(Domain).filter(Domain.id.in_(domain_ids)).all()
    if len(domains) != len(domain_ids):
        found_ids = [d.id for d in domains]
        missing_ids = [d_id for d_id in domain_ids if d_id not in found_ids]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domains not found: {missing_ids}"
        )
    
    # Move domains to group
    moved_count = 0
    for domain in domains:
        if domain.group_id != group_id:
            domain.group_id = group_id
            moved_count += 1
    
    db.commit()
    
    logger.info(f"Moved {moved_count} domains to group {group.name} by user {current_user.username}")
    
    return {
        "message": f"Successfully moved {moved_count} domains to group {group.name}",
        "moved_count": moved_count,
        "group_id": group_id
    }
