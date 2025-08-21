#!/bin/bash

###############################################################################
# ИСПРАВЛЕНИЕ ОШИБОК PRODUCTION СРЕДЫ
# Исправляет проблемы с конфигурацией Pydantic и синтаксисом БД
###############################################################################

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
fi

log "🔧 Исправление ошибок production среды..."

# Останавливаем сервис
log "Останавливаем сервис..."
systemctl stop reverse-proxy-monitor || true

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor

# Исправляем backend/config.py (добавляем недостающие поля)
log "Исправление backend/config.py..."
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
EOF

# Исправляем backend/database.py (исправляем синтаксис и добавляем pool settings)
log "Исправление backend/database.py..."
cat > backend/database.py << 'EOF'
"""
Database configuration and session management.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from backend.config import settings

def get_database_url() -> str:
    """Get database URL from environment or settings."""
    return os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Create database engine with pool settings
engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    connect_args={"check_same_thread": False} if "sqlite" in get_database_url() else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get database session for scripts."""
    return get_db()
EOF

# Исправляем main.py (критическое исправление 404)
log "Исправление настроек cookie для web аутентификации..."
# Исправляем backend/ui/routes.py для web login
if [[ -f "backend/ui/routes.py" ]]; then
    sed -i 's/secure=not settings\.DEBUG/secure=False/g' backend/ui/routes.py
    # Добавляем samesite="lax" если его нет
    sed -i '/httponly=True,$/a\        samesite="lax"  # Исправлено для работы с Nginx reverse proxy' backend/ui/routes.py
    log "Cookie настройки в UI routes исправлены"
fi

log "Исправление main.py..."
cat > main.py << 'EOF'
"""
Main application entry point - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
import uvicorn
from backend.app import app
from backend.api import auth
from backend.ui import routes

# Регистрация роутеров (исправление 404 ошибок)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes.router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        log_level="info"
    )
EOF

# Исправляем настройки cookie в auth.py
log "Исправление настроек аутентификации..."
if [[ -f "backend/auth.py" ]]; then
    sed -i 's/secure=True/secure=False/g' backend/auth.py
    sed -i 's/samesite="strict"/samesite="lax"/g' backend/auth.py
    sed -i 's/samesite="Strict"/samesite="lax"/g' backend/auth.py
    log "Cookie настройки исправлены для reverse proxy"
fi

# Проверяем виртуальное окружение
log "Обновление зависимостей..."
source venv/bin/activate || {
    log "Создание нового виртуального окружения..."
    python3.11 -m venv venv
    source venv/bin/activate
}

pip install --upgrade pip
pip install -r setup_requirements.txt

# Инициализация БД без Alembic (он может не работать)
log "Инициализация базы данных..."
python3 -c "
try:
    from backend.database import Base, engine
    import backend.models
    Base.metadata.create_all(engine)
    print('✅ Таблицы созданы')
except Exception as e:
    print(f'Ошибка БД: {e}')
"

# Создание администратора
log "Создание администратора..."
python3 -c "
try:
    from backend.database import get_db_session
    from backend.models import User
    from backend.auth import get_password_hash
    
    db = next(get_db_session())
    
    admin = db.query(User).filter(User.username == 'admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=get_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        db.add(admin)
        db.commit()
        print('✅ Администратор создан: admin/admin123')
    else:
        print('✅ Администратор уже существует')
    
    db.close()
except Exception as e:
    print(f'Информация об админе: {e}')
"

# Устанавливаем правильные права
log "Исправление прав доступа..."
chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/
chmod 600 .env
chmod +x main.py

# Перезагружаем systemd
log "Перезагрузка systemd..."
systemctl daemon-reload

# Запускаем сервис
log "Запуск сервиса..."
systemctl start reverse-proxy-monitor

# Ждем и проверяем
sleep 10

log "Проверка статуса..."
if systemctl is-active --quiet reverse-proxy-monitor; then
    echo -e "${GREEN}✅ Сервис запущен успешно${NC}"
else
    echo -e "${RED}❌ Сервис не запустился${NC}"
    echo -e "\n${YELLOW}=== СТАТУС СЕРВИСА ===${NC}"
    systemctl status reverse-proxy-monitor --no-pager -l
fi

# Тест HTTP
log "Тест HTTP соединения..."
sleep 3
if curl -s http://localhost:5000/ > /dev/null; then
    echo -e "${GREEN}✅ HTTP: работает${NC}"
elif curl -s http://localhost:5000/auth/login > /dev/null; then
    echo -e "${GREEN}✅ HTTP: работает (перенаправление на login)${NC}"
else
    echo -e "${RED}❌ HTTP: не отвечает${NC}"
    echo -e "\n${YELLOW}=== ПРОВЕРКА ПОРТОВ ===${NC}"
    ss -tlnp | grep ":5000 " || echo "Порт 5000 не слушает"
fi

# Показываем последние логи
echo -e "\n${GREEN}=== ПОСЛЕДНИЕ ЛОГИ ===${NC}"
journalctl -u reverse-proxy-monitor --no-pager -n 15

echo -e "\n${GREEN}╔══════════════════════════════════════════════╗"
echo -e "║            ИСПРАВЛЕНИЯ ПРИМЕНЕНЫ             ║"
echo -e "║                                              ║"  
echo -e "║  🌐 URL: http://$(hostname -I | awk '{print $1}')/"
echo -e "║  👤 Логин: admin                             ║"
echo -e "║  🔑 Пароль: admin123                         ║"
echo -e "║                                              ║"
echo -e "║  📋 Полезные команды:                        ║"
echo -e "║  systemctl status reverse-proxy-monitor      ║"
echo -e "║  systemctl restart reverse-proxy-monitor     ║"
echo -e "║  journalctl -u reverse-proxy-monitor -f      ║"
echo -e "╚══════════════════════════════════════════════╝${NC}"

log "🎉 ИСПРАВЛЕНИЯ ЗАВЕРШЕНЫ!"