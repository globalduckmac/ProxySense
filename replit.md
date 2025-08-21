# Overview

This project is a comprehensive reverse proxy and server monitoring system built with FastAPI. It provides web-based management of servers, domains, upstreams, and real-time monitoring. Key capabilities include server provisioning via SSH, integration with Glances for system metrics, domain management with SSL support, Nginx configuration generation, and Telegram alert notifications. The system aims to simplify server and domain management for users, offering a centralized control panel and proactive issue detection.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes

## Deployment System with Critical Fixes (August 21, 2025)
- Created comprehensive automated deployment script (`deploy.sh`) for Ubuntu 22.04
- Added production-ready configuration files (`setup_requirements.txt`, `.env.example`)
- Implemented detailed installation documentation (`install.md`)

### Critical Production Fixes Applied:
- **FIXED**: Corrected .env file generation in deployment script - removed incompatible variables (`JWT_SECRET_KEY`, `HOST`, `PORT`) that caused Pydantic validation errors
- **FIXED**: Updated `.env.example` to match actual application configuration requirements
- **FIXED**: Application user creation and directory ownership - deployment scripts now properly create `rpmonitor` user and set correct permissions
- **FIXED**: Automatic admin user creation - deployment scripts now create first admin user (admin/admin123) automatically
- **FIXED**: 404 Route Registration Issue - main.py now properly imports and registers API and UI routers to prevent all routes returning 404
- **FIXED**: Cookie Security for Reverse Proxy - authentication cookies now use `secure=False` and `samesite='lax'` for compatibility with Nginx reverse proxy
- **FIXED**: Database Connection Pool Exhaustion - increased pool from 5 to 20 connections and overflow from 10 to 30 to handle multiple SSE connections
- **FIXED**: Route Import Problems - ensured all necessary router imports are present in main.py
- **FIXED**: Cookie Settings Syntax Error - deployment scripts now use Python regex to properly replace cookie settings in UI routes, preventing syntax errors from malformed sed operations
- **FIXED**: User Model Field Issue - corrected all scripts to use `role='admin'` instead of `is_admin=True` to match actual User model structure

### Updated Deployment Scripts:
- **deploy_fixed.sh**: Comprehensive deployment with all fixes integrated
- **deploy_simple.sh**: Streamlined version with essential fixes for quick deployment
- **fix_404_routes.py**: Diagnostic script for route registration issues
- **check_routes_fix.py**: Automated fix for missing main route
- **debug_service.py**: Full service diagnostic tool

### Deployment Features:
- Automatic system updates and dependency installation
- Python 3.11 setup from PPA
- PostgreSQL database configuration
- Application user creation and security with proper ownership
- Systemd service configuration for auto-startup
- Nginx reverse proxy setup with SSL support
- UFW firewall configuration
- Log rotation and monitoring setup
- Automatic update script generation
- First admin user creation (admin/admin123)
- Fixed password change API functionality
- Enhanced user management system with modern card-based UI
- Successfully tested deployment on Ubuntu server with all fixes applied

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 for server-side rendering of HTML templates.
- **Static Assets**: CSS and JavaScript served from a dedicated static directory.
- **UI Components**: Utilizes modal-based forms, real-time dashboards, and grid-based layouts.
- **Client-side**: Employs Vanilla JavaScript for interactivity and real-time updates via Server-Sent Events.

## Backend Architecture
- **Framework**: FastAPI, leveraging async/await for high-performance API endpoints.
- **Application Structure**: Modular design with distinct packages for API, UI, and core services.
- **Authentication**: JWT-based authentication with role-based access control (admin/user roles).
- **Background Processing**: APScheduler manages periodic tasks such as server monitoring and health checks.
- **Configuration Management**: Pydantic settings are used, with robust support for environment variables.

## Data Storage Solutions
- **Primary Database**: SQLAlchemy ORM supports SQLite (default) and PostgreSQL.
- **Database Migrations**: Alembic is used for schema versioning and database migrations.
- **Data Encryption**: The Cryptography library (Fernet) encrypts sensitive data, including passwords and API keys.
- **Models**: Comprehensive data models cover servers, domains, upstreams, tasks, alerts, and user management.

## Authentication and Authorization
- **JWT Tokens**: HS256 algorithm is used for JWTs, with configurable expiration times.
- **Password Security**: Bcrypt hashing secures password storage.
- **Session Management**: HTTP-only cookies store authentication tokens.
- **Role-based Access**: Differentiates between admin and regular user roles with appropriate permission controls.

## Core Services
- **SSH Client**: Paramiko-based SSH connections handle server provisioning and management.
- **Glances Integration**: An HTTP client collects system metrics from remote Glances instances.
- **DNS Utilities**: Provides functionality for domain resolution and nameserver checking.
- **Nginx Management**: Generates and deploys Nginx configurations based on templates.
- **Task Scheduler**: Manages background job processing for monitoring and maintenance.
- **User Management**: Comprehensive web-based system for user creation, editing, activation/deactivation, password management, and role-based access control.
- **Alerting System**: Monitors server resources (CPU, Memory, Disk), server availability, and NS domain validation, sending real-time Telegram notifications with intelligent privacy masking for sensitive data (e.g., masked domain names, no IP addresses in server alerts).
- **Nginx Auto-Installation**: Automatically detects, installs, and configures Nginx on target servers for domain deployment, supporting various Linux distributions and setting up necessary directory structures.
- **Custom Nginx Templates**: Utilizes user-defined Nginx configuration templates for HTTP and SSL domains, supporting specific proxy settings and WebSocket integration.
- **Server Deletion Protection**: Implements pre-deletion validation to prevent accidental server deletion when dependent domains are active, providing clear error messages and handling cascading cleanup of related records.
- **DNS Verification**: Specifically verifies only NS (nameserver) records, aligning with policy-based nameserver validation without IP address checks.

# External Dependencies

## Third-party Services
- **Telegram Bot API**: Utilized for sending alert notifications and system status updates.
- **Glances API**: Integrated for remote server monitoring and metrics collection.
- **DNS Servers**: Configurable DNS resolution, with defaults to Google DNS and Cloudflare.

## External Libraries
- **FastAPI**: Core web framework for API development.
- **SQLAlchemy**: ORM for database interaction and query building.
- **Alembic**: Tool for managing database migrations.
- **Paramiko**: Python implementation of the SSHv2 protocol.
- **APScheduler**: Library for scheduling background tasks.
- **Cryptography**: Provides cryptographic recipes and primitives for data encryption.
- **HTTPX**: A fully featured HTTP client for Python, supporting async operations.
- **Python-jose**: Implements JSON Web Algorithms (JWA).
- **Passlib**: A password hashing library.
- **Typer**: Library for building command-line applications.
- **Pydantic**: Data validation and settings management using Python type hints.

## System Requirements
- **Python 3.7+**: The required runtime environment.
- **Database**: Supports SQLite (default for development) or PostgreSQL (recommended for production).
- **SSH Access**: Necessary for server management and provisioning functionalities.
- **Network Access**: Required for Glances API connections and DNS resolution.