"""
Application configuration management.
"""
import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    DATABASE_URL: str = "sqlite:///./app.db"
    
    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY_PATH: str = "./encryption.key"
    
    # Application
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # SSH
    SSH_TIMEOUT: int = 30
    SSH_CONNECT_TIMEOUT: int = 10
    
    # Glances
    GLANCES_POLL_INTERVAL: int = 60
    GLANCES_TIMEOUT: int = 10
    GLANCES_MAX_FAILURES: int = 3
    
    # DNS
    DNS_TIMEOUT: int = 5
    DNS_SERVERS: str = "8.8.8.8,1.1.1.1"
    
    class Config:
        env_file = ".env"
    
    @property
    def dns_servers_list(self) -> List[str]:
        """Get DNS servers as a list."""
        return [server.strip() for server in self.DNS_SERVERS.split(",")]


# Global settings instance
settings = Settings()
