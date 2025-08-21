# Overview

This is a comprehensive reverse proxy and server monitoring system built with FastAPI. The application provides web-based management of servers, domains, upstreams, and real-time monitoring capabilities. It features server provisioning through SSH, Glances integration for system metrics collection, domain management with SSL support, Nginx configuration generation, and alert notifications via Telegram.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 for server-side rendering with HTML templates
- **Static Assets**: CSS and JavaScript served from static directory
- **UI Components**: Modal-based forms, real-time dashboards, and grid-based layouts
- **Client-side**: Vanilla JavaScript with real-time updates via Server-Sent Events

## Backend Architecture
- **Framework**: FastAPI with async/await support for high-performance API endpoints
- **Application Structure**: Modular design with separate packages for API, UI, and core services
- **Authentication**: JWT-based authentication with role-based access control (admin/user roles)
- **Background Processing**: APScheduler for periodic tasks like server monitoring and health checks
- **Configuration Management**: Pydantic settings with environment variable support

## Data Storage Solutions
- **Primary Database**: SQLAlchemy ORM with support for SQLite (default) and PostgreSQL
- **Database Migrations**: Alembic for schema versioning and migrations
- **Data Encryption**: Cryptography library (Fernet) for encrypting sensitive data like passwords and API keys
- **Models**: Comprehensive data models for servers, domains, upstreams, tasks, alerts, and user management

## Authentication and Authorization
- **JWT Tokens**: HS256 algorithm with configurable expiration times
- **Password Security**: Bcrypt hashing for password storage
- **Session Management**: HTTP-only cookies for token storage
- **Role-based Access**: Admin and user roles with appropriate permission controls

## Core Services
- **SSH Client**: Paramiko-based SSH connections for server provisioning and management
- **Glances Integration**: HTTP client for collecting system metrics from remote Glances instances
- **DNS Utilities**: Domain resolution and nameserver checking functionality
- **Nginx Management**: Template-based Nginx configuration generation and deployment
- **Task Scheduler**: Background job processing for monitoring and maintenance tasks

# External Dependencies

## Third-party Services
- **Telegram Bot API**: For sending alert notifications and system status updates
- **Glances API**: Remote server monitoring and metrics collection
- **DNS Servers**: Configurable DNS resolution (defaults to Google DNS and Cloudflare)

## External Libraries
- **FastAPI**: Web framework and API development
- **SQLAlchemy**: Database ORM and query builder
- **Alembic**: Database migration management
- **Paramiko**: SSH client implementation
- **APScheduler**: Background task scheduling
- **Cryptography**: Data encryption and security
- **HTTPX**: Async HTTP client for external API calls
- **Jose**: JWT token handling
- **Passlib**: Password hashing utilities
- **Typer**: CLI management interface
- **Pydantic**: Data validation and settings management

## System Requirements
- **Python 3.7+**: Core runtime environment
- **Database**: SQLite (default) or PostgreSQL for production
- **SSH Access**: Required for server management and provisioning
- **Network Access**: For Glances API connections and DNS resolution