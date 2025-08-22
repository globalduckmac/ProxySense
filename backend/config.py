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
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production"  # Добавлено для совместимости
    ENCRYPTION_KEY: str = ""  # Добавлено для совместимости
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY_PATH: str = "./encryption.key"
    
    # Application
    DEBUG: bool = True
    ENVIRONMENT: str = "development"  # Добавлено для совместимости
    LOG_LEVEL: str = "INFO"
    
    # Database Pool Settings (добавлены для исправления)
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 60
    
    # Cookie Settings (добавлены для reverse proxy)
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    
    # Monitoring Settings (добавлены)
    SERVER_CHECK_INTERVAL: int = 300
    NS_CHECK_INTERVAL: int = 3600
    ALERT_COOLDOWN: int = 1800
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # SSH
    SSH_TIMEOUT: int = 30
    SSH_CONNECT_TIMEOUT: int = 10
    
    # Glances
    GLANCES_POLL_INTERVAL: int = 60
    GLANCES_TIMEOUT: int = 30  # Увеличен с 10 до 30 секунд
    GLANCES_MAX_FAILURES: int = 3
    
    # DNS
    DNS_TIMEOUT: int = 5
    DNS_SERVERS: str = "8.8.8.8,1.1.1.1"
    
    # Basic Authentication (для дополнительной защиты)
    BASIC_AUTH_ENABLED: bool = False
    BASIC_AUTH_USERNAME: str = "admin"
    BASIC_AUTH_PASSWORD: str = "secret"
    
    class Config:
        env_file = ".env"
    
    @property
    def dns_servers_list(self) -> List[str]:
        """Get DNS servers as a list."""
        return [server.strip() for server in self.DNS_SERVERS.split(",")]


# Global settings instance
settings = Settings()
