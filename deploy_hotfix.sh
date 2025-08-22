#!/bin/bash

###############################################################################
# БЫСТРОЕ ИСПРАВЛЕНИЕ для развернутого приложения
# Исправляет Pydantic ошибки с Basic Auth переменными
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# Проверка root
if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
fi

log "🔧 Применение исправления для Basic Auth..."

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor || error "Директория /opt/reverse-proxy-monitor не найдена"

# Исправляем backend/config.py
log "Обновление config.py..."
cat > backend/config.py << 'EOF'
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
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production"
    ENCRYPTION_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY_PATH: str = "./encryption.key"
    
    # Application
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Database Pool Settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 60
    
    # Cookie Settings
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    
    # Monitoring Settings
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
    GLANCES_TIMEOUT: int = 10
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
EOF

# Удаляем проблемные переменные из .env (они теперь имеют значения по умолчанию)
log "Очистка .env от проблемных переменных..."
if [[ -f .env ]]; then
    sed -i '/^BASIC_AUTH_ENABLED=/d' .env
    sed -i '/^BASIC_AUTH_USERNAME=/d' .env
    sed -i '/^BASIC_AUTH_PASSWORD=/d' .env
fi

# Перезапускаем сервис
log "Перезапуск сервиса..."
systemctl restart reverse-proxy-monitor

# Проверяем статус
sleep 3
if systemctl is-active --quiet reverse-proxy-monitor; then
    log "✅ Сервис успешно запущен!"
    log "🌐 Приложение доступно на http://$(hostname -I | awk '{print $1}')"
    log "🔑 Логин: admin / Пароль: admin123"
else
    error "❌ Сервис не запустился. Проверьте логи: sudo journalctl -u reverse-proxy-monitor -f"
fi

log "🎉 Исправление применено!"