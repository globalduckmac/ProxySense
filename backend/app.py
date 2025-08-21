"""
FastAPI application setup and configuration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from backend.config import settings
from backend.database import engine, Base
from backend.api import auth, servers, upstreams, domains, groups, tasks, alerts, settings as settings_api, users
from backend.ui.routes import router as ui_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Reverse Proxy & Monitor application...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Start server monitoring service
    from backend.server_monitor import monitor_service
    await monitor_service.start()
    
    # Start NS monitoring service
    from backend.ns_monitor import ns_monitor
    await ns_monitor.start()
    
    yield
    
    # Stop monitoring services
    await monitor_service.stop()
    from backend.ns_monitor import ns_monitor
    await ns_monitor.stop()
    logger.info("Shutting down Reverse Proxy & Monitor application...")


# Create FastAPI application
app = FastAPI(
    title="Reverse Proxy & Monitor",
    description="A comprehensive reverse proxy and server monitoring system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(servers.router, prefix="/api/servers", tags=["Servers"])
app.include_router(upstreams.router, prefix="/api/upstreams", tags=["Upstreams"])
app.include_router(domains.router, prefix="/api/domains", tags=["Domains"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])

# Include UI router
app.include_router(ui_router)

# Health check endpoints
@app.get("/health")
async def health_check():
    """API health check."""
    return {"status": "healthy", "service": "api"}


@app.get("/health/scheduler")
async def scheduler_health_check():
    """Scheduler health check."""
    # TODO: Implement scheduler health check logic
    return {"status": "healthy", "service": "scheduler"}


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
