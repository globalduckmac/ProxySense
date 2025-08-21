"""
Upstream management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from backend.database import get_db
from backend.models import Upstream, UpstreamTarget, User
from backend.auth import get_admin_user, get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter()


class UpstreamTargetCreate(BaseModel):
    host: str
    port: int
    weight: int = 1


class UpstreamTargetResponse(BaseModel):
    id: int
    host: str
    port: int
    weight: int
    
    class Config:
        from_attributes = True


class UpstreamCreate(BaseModel):
    name: str
    targets: List[UpstreamTargetCreate]


class UpstreamUpdate(BaseModel):
    name: Optional[str] = None
    targets: Optional[List[UpstreamTargetCreate]] = None


class UpstreamResponse(BaseModel):
    id: int
    name: str
    created_at: str
    updated_at: str
    targets: List[UpstreamTargetResponse]
    

    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[UpstreamResponse])
async def list_upstreams(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """List all upstreams."""
    upstreams = db.query(Upstream).offset(skip).limit(limit).all()
    
    # Convert to proper response format
    result = []
    for upstream in upstreams:
        targets = [UpstreamTargetResponse(
            id=target.id,
            host=target.host,
            port=target.port,
            weight=target.weight
        ) for target in upstream.targets]
        
        result.append(UpstreamResponse(
            id=upstream.id,
            name=upstream.name,
            created_at=upstream.created_at.isoformat() if upstream.created_at else "",
            updated_at=upstream.updated_at.isoformat() if upstream.updated_at else "",
            targets=targets
        ))
    
    return result


@router.post("/", response_model=UpstreamResponse)
async def create_upstream(
    request: Request,
    upstream_data: UpstreamCreate,
    db: Session = Depends(get_db)
):
    """Create a new upstream."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    # Check if upstream name already exists
    existing_upstream = db.query(Upstream).filter(Upstream.name == upstream_data.name).first()
    if existing_upstream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upstream with this name already exists"
        )
    
    if not upstream_data.targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one target is required"
        )
    
    # Create upstream
    upstream = Upstream(name=upstream_data.name)
    db.add(upstream)
    db.flush()  # Get the ID
    
    # Create targets
    for target_data in upstream_data.targets:
        target = UpstreamTarget(
            upstream_id=upstream.id,
            host=target_data.host,
            port=target_data.port,
            weight=target_data.weight
        )
        db.add(target)
    
    db.commit()
    db.refresh(upstream)
    
    logger.info(f"Upstream {upstream.name} created by user {current_user.username}")
    
    # Return properly formatted response
    return UpstreamResponse(
        id=upstream.id,
        name=upstream.name,
        created_at=upstream.created_at.isoformat() if upstream.created_at else "",
        updated_at=upstream.updated_at.isoformat() if upstream.updated_at else "",
        targets=[UpstreamTargetResponse(
            id=target.id,
            host=target.host,
            port=target.port,
            weight=target.weight
        ) for target in upstream.targets]
    )


@router.get("/{upstream_id}", response_model=UpstreamResponse)
async def get_upstream(
    upstream_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific upstream."""
    upstream = db.query(Upstream).filter(Upstream.id == upstream_id).first()
    if not upstream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upstream not found"
        )
    return upstream


@router.put("/{upstream_id}", response_model=UpstreamResponse)
async def update_upstream(
    upstream_id: int,
    upstream_data: UpstreamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update an upstream."""
    upstream = db.query(Upstream).filter(Upstream.id == upstream_id).first()
    if not upstream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upstream not found"
        )
    
    # Update name if provided
    if upstream_data.name is not None:
        # Check for name conflicts
        existing_upstream = db.query(Upstream).filter(
            Upstream.name == upstream_data.name,
            Upstream.id != upstream_id
        ).first()
        if existing_upstream:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upstream with this name already exists"
            )
        upstream.name = upstream_data.name
    
    # Update targets if provided
    if upstream_data.targets is not None:
        if not upstream_data.targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one target is required"
            )
        
        # Delete existing targets
        db.query(UpstreamTarget).filter(UpstreamTarget.upstream_id == upstream_id).delete()
        
        # Create new targets
        for target_data in upstream_data.targets:
            target = UpstreamTarget(
                upstream_id=upstream_id,
                host=target_data.host,
                port=target_data.port,
                weight=target_data.weight
            )
            db.add(target)
    
    db.commit()
    db.refresh(upstream)
    
    logger.info(f"Upstream {upstream.name} updated by user {current_user.username}")
    return upstream


@router.delete("/{upstream_id}")
async def delete_upstream(
    upstream_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete an upstream."""
    upstream = db.query(Upstream).filter(Upstream.id == upstream_id).first()
    if not upstream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upstream not found"
        )
    
    # Check if upstream is used by any domains
    if upstream.domains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete upstream that is used by domains"
        )
    
    upstream_name = upstream.name
    db.delete(upstream)
    db.commit()
    
    logger.info(f"Upstream {upstream_name} deleted by user {current_user.username}")
    return {"message": "Upstream deleted successfully"}
