"""
SQLAlchemy database models.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON,
    Table, Enum as SQLEnum, Float, LargeBinary
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import enum

from backend.database import Base


class AuthType(enum.Enum):
    PASSWORD = "password"
    SSH_KEY = "ssh_key"


class GlancesAuthType(enum.Enum):
    NONE = "none"
    BASIC = "basic"
    TOKEN = "token"


class ServerStatus(enum.Enum):
    PROVISIONING = "provisioning"
    OK = "ok"
    UNREACHABLE = "unreachable"


class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AlertLevel(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Association table for server tags
server_tags = Table(
    'server_tags',
    Base.metadata,
    Column('server_id', Integer, ForeignKey('servers.id')),
    Column('tag', String(50))
)


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Server(Base):
    """Server model."""
    __tablename__ = "servers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    host: Mapped[str] = mapped_column(String(255))
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(100))
    auth_type: Mapped[AuthType] = mapped_column(SQLEnum(AuthType))
    password: Mapped[Optional[str]] = mapped_column(LargeBinary, nullable=True)  # Encrypted
    ssh_key: Mapped[Optional[str]] = mapped_column(LargeBinary, nullable=True)  # Encrypted
    ssh_key_passphrase: Mapped[Optional[str]] = mapped_column(LargeBinary, nullable=True)  # Encrypted
    
    # Glances configuration
    glances_scheme: Mapped[str] = mapped_column(String(10), default="http")
    glances_host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Defaults to host
    glances_port: Mapped[int] = mapped_column(Integer, default=61208)
    glances_path: Mapped[str] = mapped_column(String(255), default="/api/4/all")
    glances_auth_type: Mapped[GlancesAuthType] = mapped_column(SQLEnum(GlancesAuthType), default=GlancesAuthType.NONE)
    glances_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    glances_password: Mapped[Optional[str]] = mapped_column(LargeBinary, nullable=True)  # Encrypted
    glances_token: Mapped[Optional[str]] = mapped_column(LargeBinary, nullable=True)  # Encrypted
    
    # Status and monitoring
    status: Mapped[ServerStatus] = mapped_column(SQLEnum(ServerStatus), default=ServerStatus.PROVISIONING)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    metrics: Mapped[List["ServerMetric"]] = relationship("ServerMetric", back_populates="server", cascade="all, delete-orphan")
    domains: Mapped[List["Domain"]] = relationship("Domain", back_populates="server")


class ServerMetric(Base):
    """Server metrics model."""
    __tablename__ = "server_metrics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_id: Mapped[int] = mapped_column(Integer, ForeignKey("servers.id"))
    
    # System metrics
    cpu_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    load_1min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    load_5min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    load_15min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uptime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Seconds
    
    # Raw data for future processing
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    server: Mapped["Server"] = relationship("Server", back_populates="metrics")


class Upstream(Base):
    """Upstream model."""
    __tablename__ = "upstreams"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    targets: Mapped[List["UpstreamTarget"]] = relationship("UpstreamTarget", back_populates="upstream", cascade="all, delete-orphan")
    domains: Mapped[List["Domain"]] = relationship("Domain", back_populates="upstream")


class UpstreamTarget(Base):
    """Upstream target model."""
    __tablename__ = "upstream_targets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    upstream_id: Mapped[int] = mapped_column(Integer, ForeignKey("upstreams.id"))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    
    # Relationships
    upstream: Mapped["Upstream"] = relationship("Upstream", back_populates="targets")


class DomainGroup(Base):
    """Domain group model."""
    __tablename__ = "domain_groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    domains: Mapped[List["Domain"]] = relationship("Domain", back_populates="group")


class Domain(Base):
    """Domain model."""
    __tablename__ = "domains"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    server_id: Mapped[int] = mapped_column(Integer, ForeignKey("servers.id"))
    ssl: Mapped[bool] = mapped_column(Boolean, default=False)
    upstream_id: Mapped[int] = mapped_column(Integer, ForeignKey("upstreams.id"))
    group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("domain_groups.id"), nullable=True)
    ns_policy: Mapped[str] = mapped_column(String(100), default="dnspod")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_ns_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    server: Mapped["Server"] = relationship("Server", back_populates="domains")
    upstream: Mapped["Upstream"] = relationship("Upstream", back_populates="domains")
    group: Mapped[Optional["DomainGroup"]] = relationship("DomainGroup", back_populates="domains")
    ns_checks: Mapped[List["NSCheck"]] = relationship("NSCheck", back_populates="domain", cascade="all, delete-orphan")


class NSCheck(Base):
    """NS check model."""
    __tablename__ = "ns_checks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    domain_id: Mapped[int] = mapped_column(Integer, ForeignKey("domains.id"))
    ns_servers: Mapped[list] = mapped_column(JSON)  # List of NS servers
    is_valid: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    domain: Mapped["Domain"] = relationship("Domain", back_populates="ns_checks")


class Task(Base):
    """Task model."""
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Task metadata
    task_type: Mapped[str] = mapped_column(String(100))  # ssh_check, deploy_proxy, etc.
    server_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("servers.id"), nullable=True)
    domain_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("domains.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    logs: Mapped[List["TaskLog"]] = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")


class TaskLog(Base):
    """Task log model."""
    __tablename__ = "task_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    level: Mapped[str] = mapped_column(String(20))  # INFO, WARNING, ERROR, etc.
    source: Mapped[str] = mapped_column(String(100))  # ssh, certbot, nginx, etc.
    message: Mapped[str] = mapped_column(Text)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    return_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="logs")


class Alert(Base):
    """Alert model."""
    __tablename__ = "alerts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    level: Mapped[AlertLevel] = mapped_column(SQLEnum(AlertLevel))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    
    # Alert metadata
    alert_type: Mapped[str] = mapped_column(String(100))  # server_down, ssl_error, etc.
    server_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("servers.id"), nullable=True)
    domain_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("domains.id"), nullable=True)
    
    # Notification status
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    """Setting model."""
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[Optional[str]] = mapped_column(LargeBinary, nullable=True)  # Encrypted for sensitive values
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
