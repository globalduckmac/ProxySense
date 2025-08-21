"""
User management API endpoints.
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth import get_current_user_from_cookie, get_password_hash, verify_password
from backend.database import get_db
from backend.models import User

logger = logging.getLogger(__name__)

router = APIRouter()

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "user"

class UpdatePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str

@router.get("/", response_model=List[UserResponse])
async def get_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get all users (admin only) or current user."""
    if current_user.role == "admin":
        users = db.query(User).all()
    else:
        users = [current_user]
    
    return [UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at
    ) for user in users]

@router.post("/", response_model=UserResponse)
async def create_user(
    user_request: CreateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Create a new user (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email already exists (if provided)
    if user_request.email:
        existing_email = db.query(User).filter(User.email == user_request.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create new user
    hashed_password = get_password_hash(user_request.password)
    user = User(
        username=user_request.username,
        password_hash=hashed_password,
        email=user_request.email,
        role=user_request.role,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"User created: {user.username} (role: {user.role}) by admin {current_user.username}")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at
    )

@router.put("/{user_id}/password")
async def update_user_password(
    user_id: int,
    password_request: UpdatePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update user password."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # If not admin, verify current password
    if current_user.role != "admin":
        if not password_request.current_password:
            raise HTTPException(status_code=400, detail="Current password required")
        if not verify_password(password_request.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid current password")
    
    # Update password
    target_user.password_hash = get_password_hash(password_request.new_password)
    db.commit()
    
    logger.info(f"Password updated for user {target_user.username} by {current_user.username}")
    
    return {"message": "Password updated successfully"}

class UpdateStatusRequest(BaseModel):
    is_active: bool

@router.put("/{user_id}/status")
async def update_user_status(
    user_id: int,
    status_request: UpdateStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update user active status (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    
    user.is_active = status_request.is_active
    db.commit()
    
    action = "activated" if status_request.is_active else "deactivated"
    logger.info(f"User {user.username} {action} by admin {current_user.username}")
    
    return {"message": f"User {action} successfully"}

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Delete a user (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    
    logger.info(f"User {user.username} deleted by admin {current_user.username}")
    
    return {"message": "User deleted successfully"}

# Web UI endpoints
@router.post("/ui/create")
async def create_user_ui(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    role: str = Form("user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Create user via web form."""
    try:
        create_request = CreateUserRequest(
            username=username,
            password=password,
            email=email if email else None,
            role=role
        )
        await create_user(create_request, request, db, current_user)
        return RedirectResponse(url="/users?success=User created successfully", status_code=303)
    except HTTPException as e:
        return RedirectResponse(url=f"/users?error={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return RedirectResponse(url="/users?error=Failed to create user", status_code=303)

@router.post("/ui/{user_id}/password")
async def update_password_ui(
    user_id: int,
    request: Request,
    current_password: str = Form(None),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update password via web form."""
    try:
        update_request = UpdatePasswordRequest(
            current_password=current_password if current_password else None,
            new_password=new_password
        )
        await update_user_password(user_id, update_request, request, db, current_user)
        return RedirectResponse(url="/users?success=Password updated successfully", status_code=303)
    except HTTPException as e:
        return RedirectResponse(url=f"/users?error={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return RedirectResponse(url="/users?error=Failed to update password", status_code=303)

@router.post("/ui/{user_id}/toggle")
async def toggle_user_status_ui(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Toggle user status via web form."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/users?error=User not found", status_code=303)
        
        new_status = not user.is_active
        status_request = UpdateStatusRequest(is_active=new_status)
        await update_user_status(user_id, status_request, request, db, current_user)
        action = "activated" if new_status else "deactivated"
        return RedirectResponse(url=f"/users?success=User {action} successfully", status_code=303)
    except HTTPException as e:
        return RedirectResponse(url=f"/users?error={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"Error toggling user status: {e}")
        return RedirectResponse(url="/users?error=Failed to update user status", status_code=303)

@router.post("/ui/{user_id}/delete")
async def delete_user_ui(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Delete user via web form."""
    try:
        await delete_user(user_id, request, db, current_user)
        return RedirectResponse(url="/users?success=User deleted successfully", status_code=303)
    except HTTPException as e:
        return RedirectResponse(url=f"/users?error={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return RedirectResponse(url="/users?error=Failed to delete user", status_code=303)