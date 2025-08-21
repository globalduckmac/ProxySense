"""
Main entry point for the Reverse Proxy & Monitor application.
"""
import uvicorn
from backend.app import app

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        access_log=True
    )
