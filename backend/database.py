"""
Database configuration and session management.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from backend.config import settings

def get_database_url() -> str:
    """Get database URL from environment or settings."""
    return os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Create database engine
engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in get_database_url() else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
