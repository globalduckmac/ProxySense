# Overview

This project is a comprehensive reverse proxy and server monitoring system built with FastAPI. It provides web-based management of servers, domains, upstreams, and real-time monitoring. Key capabilities include server provisioning via SSH, integration with Glances for system metrics, domain management with SSL support, Nginx configuration generation, and Telegram alert notifications. The system aims to simplify server and domain management for users, offering a centralized control panel and proactive issue detection.

# User Preferences

Preferred communication style: Simple, everyday language.

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