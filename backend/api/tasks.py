"""
Task management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json
import logging

from backend.database import get_db
from backend.models import Task, TaskLog, TaskStatus, User
from backend.auth import get_admin_user, get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter()


class TaskResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: TaskStatus
    progress: int
    result: Optional[dict]
    error_message: Optional[str]
    task_type: str
    server_id: Optional[int]
    domain_id: Optional[int]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TaskLogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    source: str
    message: str
    stdout: Optional[str]
    stderr: Optional[str]
    return_code: Optional[int]
    
    class Config:
        from_attributes = True


class TaskDetailResponse(BaseModel):
    task: TaskResponse
    logs: List[TaskLogResponse]


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    status: Optional[TaskStatus] = None,
    task_type: Optional[str] = None,
    server_id: Optional[int] = None,
    domain_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """List tasks with optional filtering."""
    query = db.query(Task)
    
    if status is not None:
        query = query.filter(Task.status == status)
    if task_type is not None:
        query = query.filter(Task.task_type == task_type)
    if server_id is not None:
        query = query.filter(Task.server_id == server_id)
    if domain_id is not None:
        query = query.filter(Task.domain_id == domain_id)
    
    tasks = (
        query
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return tasks


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific task with logs."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Get task logs
    logs = (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.timestamp.asc())
        .all()
    )
    
    return TaskDetailResponse(
        task=task,
        logs=logs
    )


@router.get("/{task_id}/logs", response_model=List[TaskLogResponse])
async def get_task_logs(
    task_id: int,
    skip: int = 0,
    limit: int = 1000,
    level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get logs for a specific task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    query = db.query(TaskLog).filter(TaskLog.task_id == task_id)
    
    if level:
        query = query.filter(TaskLog.level == level.upper())
    
    logs = (
        query
        .order_by(TaskLog.timestamp.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return logs


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete a task and its logs."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check if task is running
    if task.status == TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running task"
        )
    
    task_name = task.name
    db.delete(task)
    db.commit()
    
    logger.info(f"Task {task_name} deleted by user {current_user.username}")
    return {"message": "Task deleted successfully"}


@router.get("/{task_id}/stream")
async def stream_task_logs(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db)
):
    """Stream task logs via Server-Sent Events."""
    # Check cookie authentication first
    current_user = await get_current_user_from_cookie(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or insufficient permissions"
        )
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    async def event_generator():
        """Generate Server-Sent Events for task logs."""
        last_log_id = 0
        
        while True:
            try:
                # Get new logs since last check
                new_logs = (
                    db.query(TaskLog)
                    .filter(
                        TaskLog.task_id == task_id,
                        TaskLog.id > last_log_id
                    )
                    .order_by(TaskLog.timestamp.asc())
                    .all()
                )
                
                # Send new logs
                for log in new_logs:
                    log_data = {
                        "id": log.id,
                        "timestamp": log.timestamp.isoformat(),
                        "level": log.level,
                        "source": log.source,
                        "message": log.message,
                        "stdout": log.stdout,
                        "stderr": log.stderr,
                        "return_code": log.return_code
                    }
                    
                    yield f"data: {json.dumps(log_data)}\n\n"
                    last_log_id = log.id
                
                # Check task status
                current_task = db.query(Task).filter(Task.id == task_id).first()
                if current_task:
                    # Send task status update
                    status_data = {
                        "type": "status",
                        "status": current_task.status.value,
                        "progress": current_task.progress,
                        "error_message": current_task.error_message
                    }
                    yield f"data: {json.dumps(status_data)}\n\n"
                    
                    # Stop streaming if task is completed or failed
                    if current_task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        break
                
                # Wait before checking for new logs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in task log stream: {e}")
                error_data = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable Nginx buffering
        }
    )


@router.get("/{task_id}/download")
async def download_task_logs(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Download task logs as a text file."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Get all logs for the task
    logs = (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.timestamp.asc())
        .all()
    )
    
    # Generate log content
    log_content = f"Task: {task.name}\n"
    log_content += f"Description: {task.description or 'N/A'}\n"
    log_content += f"Status: {task.status.value}\n"
    log_content += f"Created: {task.created_at}\n"
    log_content += f"Started: {task.started_at or 'N/A'}\n"
    log_content += f"Completed: {task.completed_at or 'N/A'}\n"
    log_content += f"Progress: {task.progress}%\n"
    if task.error_message:
        log_content += f"Error: {task.error_message}\n"
    log_content += "\n" + "="*80 + "\n\n"
    
    for log in logs:
        log_content += f"[{log.timestamp}] {log.level} ({log.source}): {log.message}\n"
        if log.stdout:
            log_content += f"STDOUT: {log.stdout}\n"
        if log.stderr:
            log_content += f"STDERR: {log.stderr}\n"
        if log.return_code is not None:
            log_content += f"Return Code: {log.return_code}\n"
        log_content += "\n"
    
    # Create filename
    safe_task_name = "".join(c for c in task.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"task_{task_id}_{safe_task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    return StreamingResponse(
        iter([log_content.encode()]),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/stats/overview")
async def get_task_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get task statistics overview."""
    from sqlalchemy import func
    
    # Get task counts by status
    status_counts = (
        db.query(Task.status, func.count(Task.id))
        .group_by(Task.status)
        .all()
    )
    
    # Get task counts by type
    type_counts = (
        db.query(Task.task_type, func.count(Task.id))
        .group_by(Task.task_type)
        .all()
    )
    
    # Get recent tasks
    recent_tasks = (
        db.query(Task)
        .order_by(Task.created_at.desc())
        .limit(10)
        .all()
    )
    
    return {
        "status_counts": {status.value: count for status, count in status_counts},
        "type_counts": {task_type: count for task_type, count in type_counts},
        "recent_tasks": recent_tasks,
        "total_tasks": sum(count for _, count in status_counts)
    }


@router.post("/cleanup")
async def cleanup_old_tasks(
    days: int = 30,
    status: Optional[TaskStatus] = TaskStatus.COMPLETED,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Clean up old completed tasks."""
    from datetime import timedelta
    
    if days < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be at least 1"
        )
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Count tasks to be deleted
    query = db.query(Task).filter(Task.created_at < cutoff_date)
    if status:
        query = query.filter(Task.status == status)
    
    task_count = query.count()
    
    if task_count == 0:
        return {"message": "No tasks to clean up", "deleted_count": 0}
    
    # Delete tasks (logs will be deleted via cascade)
    deleted_count = query.delete()
    db.commit()
    
    logger.info(f"Cleaned up {deleted_count} old tasks by user {current_user.username}")
    
    return {
        "message": f"Successfully cleaned up {deleted_count} tasks older than {days} days",
        "deleted_count": deleted_count
    }
