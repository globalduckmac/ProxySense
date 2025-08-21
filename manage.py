"""
CLI management interface for the Reverse Proxy & Monitor application.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database import get_database_url
from backend.models import Base, User
from backend.auth import get_password_hash
from backend.crypto import generate_key, save_key

app = typer.Typer()


@app.command()
def init_db():
    """Initialize the database and run migrations."""
    typer.echo("Initializing database...")
    
    # Create database directory if using SQLite
    db_url = get_database_url()
    if db_url.startswith("sqlite:"):
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Run Alembic migrations
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    typer.echo("Database initialized successfully!")


@app.command()
def migrate(message: str = "Auto migration"):
    """Create a new migration."""
    typer.echo(f"Creating migration: {message}")
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, message=message, autogenerate=True)
    typer.echo("Migration created successfully!")


@app.command()
def upgrade():
    """Apply pending migrations."""
    typer.echo("Applying migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    typer.echo("Migrations applied successfully!")


@app.command()
def run_api():
    """Run the API server."""
    import uvicorn
    typer.echo("Starting API server on 0.0.0.0:5000...")
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=5000,
        access_log=True
    )


@app.command()
def run_scheduler():
    """Run the background scheduler."""
    typer.echo("Starting scheduler...")
    from backend.scheduler import main
    asyncio.run(main())


@app.command()
def dev():
    """Run in development mode (API + scheduler)."""
    import subprocess
    import signal
    import time
    
    typer.echo("Starting development environment...")
    
    # Start API server
    api_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", 
        "backend.app:app", 
        "--host", "0.0.0.0", 
        "--port", "5000", 
        "--reload"
    ])
    
    # Start scheduler
    scheduler_proc = subprocess.Popen([
        sys.executable, "manage.py", "run-scheduler"
    ])
    
    def signal_handler(sig, frame):
        typer.echo("Shutting down...")
        api_proc.terminate()
        scheduler_proc.terminate()
        api_proc.wait()
        scheduler_proc.wait()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        api_proc.wait()
        scheduler_proc.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)


@app.command()
def create_admin(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
    email: str = typer.Option(..., prompt=True)
):
    """Create an admin user."""
    engine = create_engine(get_database_url())
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            typer.echo(f"User {username} already exists!")
            return
        
        # Create new admin user
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role="admin",
            is_active=True
        )
        db.add(user)
        db.commit()
        typer.echo(f"Admin user {username} created successfully!")


@app.command()
def encrypt_keygen():
    """Generate a new encryption key."""
    key = generate_key()
    save_key(key)
    typer.echo("Encryption key generated and saved!")


if __name__ == "__main__":
    app()
