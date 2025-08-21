# Overview

This is a comprehensive reverse proxy and server monitoring system built with FastAPI. The application provides web-based management of servers, domains, upstreams, and real-time monitoring capabilities. It features server provisioning through SSH, Glances integration for system metrics collection, domain management with SSL support, Nginx configuration generation, and alert notifications via Telegram.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (August 2025)

## Nginx Auto-Installation for Domain Deployment Fix
- **Date**: August 21, 2025
- **Change**: Fixed domain deployment failures by adding automatic Nginx installation and configuration
- **Features**: 
  - **Automatic Nginx Detection**: Checks if Nginx is installed before deployment
  - **Multi-OS Installation Support**: Handles Ubuntu/Debian (apt) and CentOS/RHEL (yum/dnf) package managers
  - **Directory Structure Setup**: Creates sites-available and sites-enabled directories automatically
  - **Configuration Integration**: Ensures nginx.conf includes sites-enabled directory
  - **Enhanced Logging**: Detailed deployment logs for troubleshooting
  - **SSL Logic Fix**: Creates HTTP config first, then upgrades to HTTPS after SSL certificate
  - **Certbot Installation**: Automatic certbot installation via snap for better reliability
- **Implementation**: Modified `run_deploy_domain_task()` in `backend/api/domains.py` with comprehensive pre-deployment checks
- **Result**: Domain deployment now works on fresh servers without pre-installed Nginx, including SSL domains

## Complete Alert System Implementation

## Complete Alert System Implementation
- **Date**: August 21, 2025
- **Change**: Implemented comprehensive monitoring and alerting system with Telegram notifications
- **Features**: 
  - **Server Resource Monitoring**: CPU (85%), Memory (90%), Disk (85%) threshold alerts
  - **Server Availability Monitoring**: Alerts when servers become unreachable (3+ consecutive failures)
  - **NS Domain Monitoring**: Continuous nameserver validation against configured policies
  - **Real-time Telegram Notifications**: All alerts automatically sent to Telegram with emojis and detailed information
  - **Alert State Management**: Prevents duplicate alerts, sends recovery notifications
  - **Comprehensive Coverage**: NS changes, server availability, resource usage alerts
- **Implementation**: Enhanced `backend/server_monitor.py` and `backend/ns_monitor.py` with alert creation, state tracking, and Telegram integration
- **Result**: Complete alerting system operational - NS record changes, server availability, CPU load, memory usage, and disk space alerts working with Telegram notifications

## Custom Nginx Configuration Templates Implementation
- **Date**: August 21, 2025
- **Change**: Implemented user's custom Nginx configuration templates for HTTP and SSL domains
- **Features**: 
  - Custom HTTP-only template with specific proxy settings and WebSocket support
  - Custom SSL template with dual HTTP/HTTPS blocks and Let's Encrypt integration
  - Direct proxy_pass to upstream targets instead of upstream blocks
  - Russian comments and user's specific proxy configuration preferences
- **Implementation**: Updated `backend/nginx_templates.py` with new `_generate_http_config()` and `_generate_ssl_config()` methods
- **Result**: Domain configurations now use user's exact Nginx templates with proper proxy settings

## Server Monitoring System Implementation
- **Date**: August 21, 2025
- **Change**: Implemented comprehensive automatic server monitoring system
- **Features**: 
  - Background monitoring service checking server availability every 30 seconds
  - Real-time status updates on web interface every 10 seconds
  - Last check timestamp display on server cards
  - Database column `last_check_at` added to track monitoring times
- **Implementation**: Created `backend/server_monitor.py` service, API endpoint `/api/servers/status`, JavaScript auto-update functions
- **Result**: Working automatic server availability monitoring with real-time UI updates

## NS Monitoring System Implementation
- **Date**: August 21, 2025
- **Change**: Implemented continuous NS (nameserver) monitoring system
- **Features**: 
  - Background NS monitoring service checking domain nameservers every 5 minutes
  - Database column `last_ns_check_at` added to domains table
  - Automatic NS verification against configured policies (e.g., "dnspod")
  - Historical NS check records stored in `ns_checks` table
- **Implementation**: Created `backend/ns_monitor.py` service, integrated with app lifecycle
- **Result**: Continuous NS monitoring working alongside server monitoring

## Group Management Authentication Fix
- **Date**: August 21, 2025
- **Change**: Fixed 401 Unauthorized error when creating domain groups
- **Implementation**: Updated `backend/api/groups.py` to use cookie-based authentication like other UI endpoints
- **Result**: Group creation now works properly from web interface

## Glances API Version Update & Server Monitoring Enhancement
- **Date**: August 21, 2025
- **Change**: Fixed Glances API version issues and added individual server monitoring pages
- **Glances API Fix**: Updated from `/api/3/` to `/api/4/` across all components (models, client, existing servers)
- **Authentication Fix**: Resolved 401 Unauthorized errors in dashboard stream and stats endpoints
- **New Feature**: Added dedicated server monitoring pages with real-time Glances data visualization
- **Implementation**: 
  - Updated `backend/models.py`, `backend/glances_client.py`, `backend/api/servers.py` for API v4
  - Modified existing server database record to use correct API path
  - Added `/servers/{id}/monitor` route with comprehensive system metrics display
  - Fixed dashboard authentication to prevent 401 errors
  - Added "Monitor" button to server management interface
- **Result**: Working Glances integration with real-time CPU, memory, disk, and process monitoring

## DNS Verification System Update
- **Date**: August 21, 2025
- **Change**: Modified DNS verification to check only NS (nameserver) records instead of A records
- **Reason**: User requirement to verify only nameserver policies (e.g., "dnspod") without IP address validation
- **Implementation**: Updated `backend/dns_utils.py` and `backend/api/domains.py` to remove A record checking
- **Frontend**: Modified `templates/domains.html` JavaScript to display only NS verification results

## Authentication System Migration
- **Date**: August 21, 2025  
- **Change**: Migrated all domain, server, and group management endpoints from JWT to cookie-based authentication
- **Affected Endpoints**: Domain creation, DNS verification, server probe operations, group management
- **Implementation**: Replaced `get_admin_user` dependency with `get_current_user_from_cookie` for web UI operations
- **Result**: Resolved 403/401 Forbidden/Unauthorized errors in web interface operations

## Server Management Enhancements
- **Date**: August 21, 2025
- **Achievement**: Successfully installed and configured Glances monitoring on server "Tony" (109.120.150.248:22)
- **Configuration**: Glances running on port 61208 with systemd service management
- **SSH Integration**: Enhanced SSH connection logging with detailed Paramiko connection status for real-time monitoring

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