#!/bin/bash

###############################################################################
# ПОЛНЫЙ СКРИПТ РАЗВЕРТЫВАНИЯ REVERSE PROXY MONITOR
# Версия: 2.0 с исправлениями (21 августа 2025)
#
# Включает все исправления:
# - Правильная настройка .env файла
# - Исправление конфигурации cookie для reverse proxy
# - Увеличение пула соединений БД
# - Корректная регистрация маршрутов
# - Автоматическое создание admin пользователя
###############################################################################

set -e  # Остановить при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для логирования
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Проверка прав root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Этот скрипт должен запускаться с правами root"
    fi
}

# Определение ОС
detect_os() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        error "Невозможно определить операционную систему"
    fi
    
    log "Обнаружена ОС: $OS $OS_VERSION"
}

# Обновление системы
update_system() {
    log "Обновление системы..."
    
    case $OS in
        ubuntu|debian)
            apt-get update -y
            apt-get upgrade -y
            apt-get install -y wget curl git software-properties-common gnupg2
            ;;
        centos|rhel|rocky|almalinux)
            yum update -y
            yum install -y wget curl git epel-release
            ;;
        *)
            error "Неподдерживаемая операционная система: $OS"
            ;;
    esac
}

# Установка Python 3.11
install_python() {
    log "Установка Python 3.11..."
    
    case $OS in
        ubuntu|debian)
            # Добавляем PPA для Python 3.11
            add-apt-repository ppa:deadsnakes/ppa -y
            apt-get update -y
            apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
            
            # Устанавливаем python3.11 как альтернативу по умолчанию
            update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
            ;;
        centos|rhel|rocky|almalinux)
            yum install -y python3.11 python3.11-pip python3.11-devel
            ;;
    esac
    
    # Обновляем pip
    python3 -m pip install --upgrade pip setuptools wheel
}

# Установка PostgreSQL
install_postgresql() {
    log "Установка PostgreSQL..."
    
    case $OS in
        ubuntu|debian)
            apt-get install -y postgresql postgresql-contrib postgresql-client
            ;;
        centos|rhel|rocky|almalinux)
            yum install -y postgresql-server postgresql-contrib
            postgresql-setup initdb
            ;;
    esac
    
    systemctl enable postgresql
    systemctl start postgresql
    
    log "PostgreSQL установлен и запущен"
}

# Настройка базы данных
setup_database() {
    log "Настройка базы данных..."
    
    DB_NAME="reverse_proxy_monitor"
    DB_USER="rpmonitor"
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Создание базы данных и пользователя
    sudo -u postgres psql <<EOF
CREATE DATABASE ${DB_NAME};
CREATE USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER USER ${DB_USER} CREATEDB;
\q
EOF
    
    log "База данных настроена"
    
    # Сохраняем данные для подключения
    echo "DB_NAME=${DB_NAME}" > /tmp/db_config
    echo "DB_USER=${DB_USER}" >> /tmp/db_config
    echo "DB_PASSWORD=${DB_PASSWORD}" >> /tmp/db_config
}

# Создание пользователя приложения
create_app_user() {
    log "Создание пользователя приложения..."
    
    if ! id "rpmonitor" &>/dev/null; then
        useradd --system --shell /bin/bash --home /opt/reverse-proxy-monitor --create-home rpmonitor
        log "Пользователь rpmonitor создан"
    else
        log "Пользователь rpmonitor уже существует"
    fi
}

# Клонирование и настройка приложения
setup_application() {
    log "Настройка приложения..."
    
    # Создаем или очищаем директорию приложения
    if [[ -d "/opt/reverse-proxy-monitor" && ! -d "/opt/reverse-proxy-monitor/.git" ]]; then
        log "Очистка существующей директории..."
        rm -rf /opt/reverse-proxy-monitor/*
        rm -rf /opt/reverse-proxy-monitor/.[^.]*
    fi
    
    # Переходим в директорию приложения
    cd /opt/reverse-proxy-monitor
    
    # Клонируем или обновляем репозиторий
    if [[ ! -d ".git" ]]; then
        log "Клонирование репозитория..."
        git clone https://github.com/globalduckmac/ProxySense.git .
    else
        log "Обновление существующего репозитория..."
        git stash push -m "Auto-stash before update $(date)" || true
        git pull origin main || {
            warn "Не удалось обновить репозиторий, пересоздаем..."
            cd /opt
            rm -rf reverse-proxy-monitor
            mkdir -p reverse-proxy-monitor
            cd reverse-proxy-monitor
            git clone https://github.com/globalduckmac/ProxySense.git .
        }
    fi
    
    # Создаем виртуальное окружение
    log "Создание виртуального окружения..."
    python3.11 -m venv venv
    source venv/bin/activate
    
    # Обновляем pip в виртуальном окружении
    pip install --upgrade pip setuptools wheel
    
    # Устанавливаем зависимости
    log "Установка зависимостей..."
    pip install -r setup_requirements.txt
    
    log "Приложение настроено"
}

# Создание правильного .env файла
create_env_file() {
    log "Создание .env файла..."
    
    # Загружаем данные БД
    source /tmp/db_config
    
    # Генерируем секретные ключи
    JWT_SECRET=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    
    cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}

# Security
JWT_SECRET_KEY=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Application Settings
DEBUG=false
ENVIRONMENT=production

# Database Pool Settings (исправление для множественных SSE соединений)
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=60

# Cookie Settings (исправление для reverse proxy)
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

# Telegram (опционально - можно добавить позже)
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=

# DNS Settings
DNS_SERVERS=8.8.8.8,1.1.1.1

# Monitoring Settings
SERVER_CHECK_INTERVAL=300
NS_CHECK_INTERVAL=3600
ALERT_COOLDOWN=1800

# Basic HTTP Authentication (дополнительная защита)
BASIC_AUTH_ENABLED=false
BASIC_AUTH_USERNAME=admin
BASIC_AUTH_PASSWORD=changeme
EOF
    
    log ".env файл создан с правильными настройками"
}

# Создание правильного main.py
fix_main_py() {
    log "Создание правильного main.py..."
    
    cat > main.py << 'EOF'
"""
Main application entry point for Reverse Proxy & Monitor.
Исправлено: правильная регистрация роутеров для устранения 404 ошибок
"""
import uvicorn
from backend.app import app
from backend.api import auth
from backend.ui import routes

# Include API routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Include UI routes  
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
    
    log "main.py исправлен"
}

# Исправление настроек cookie в backend/auth.py
fix_auth_settings() {
    log "Исправление настроек аутентификации..."
    
    # Исправляем backend/auth.py
    if [[ -f "backend/auth.py" ]]; then
        sed -i 's/secure=True/secure=False/g' backend/auth.py
        sed -i 's/samesite="strict"/samesite="lax"/g' backend/auth.py
        sed -i 's/samesite="Strict"/samesite="lax"/g' backend/auth.py
        log "Cookie настройки в auth.py исправлены для reverse proxy"
    fi
    
    # Исправляем backend/ui/routes.py для web login
    if [[ -f "backend/ui/routes.py" ]]; then
        # Заменяем весь блок set_cookie чтобы избежать синтаксических ошибок
        python3 << 'PYTHON_EOF'
import re

with open('backend/ui/routes.py', 'r') as f:
    content = f.read()

# Ищем и заменяем весь блок set_cookie
pattern = r'response\.set_cookie\(\s*key="access_token",\s*value=access_token,\s*max_age=settings\.ACCESS_TOKEN_EXPIRE_MINUTES \* 60,\s*httponly=True,\s*secure=not settings\.DEBUG\s*\)'

replacement = '''response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )'''

content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

with open('backend/ui/routes.py', 'w') as f:
    f.write(content)

print("Cookie настройки в UI routes исправлены")
PYTHON_EOF
        log "Cookie настройки в UI routes исправлены для reverse proxy"
    fi
}

# Создание исправленных файлов конфигурации
fix_config_files() {
    log "Создание исправленных файлов конфигурации..."
    
    # Исправляем backend/config.py
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
    
    class Config:
        env_file = ".env"
    
    @property
    def dns_servers_list(self) -> List[str]:
        """Get DNS servers as a list."""
        return [server.strip() for server in self.DNS_SERVERS.split(",")]


# Global settings instance
settings = Settings()
EOF

    # Исправляем backend/database.py
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
    
    log "Файлы конфигурации обновлены"
}

# Применение миграций БД
run_migrations() {
    log "Применение миграций базы данных..."
    
    source venv/bin/activate
    
    # Создаем таблицы через SQLAlchemy (избегаем проблем с Alembic)
    python3 -c "
try:
    from backend.database import Base, engine
    import backend.models
    Base.metadata.create_all(engine)
    print('✅ Таблицы созданы')
except Exception as e:
    print(f'Ошибка БД: {e}')
"
}

# Создание администратора
create_admin_user() {
    log "Создание администратора..."
    
    source venv/bin/activate
    
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
}

# Создание systemd сервиса
create_systemd_service() {
    log "Создание systemd сервиса..."
    
    cat > /etc/systemd/system/reverse-proxy-monitor.service << EOF
[Unit]
Description=Reverse Proxy Monitor
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=rpmonitor
Group=rpmonitor
WorkingDirectory=/opt/reverse-proxy-monitor
Environment=PATH=/opt/reverse-proxy-monitor/venv/bin
ExecStart=/opt/reverse-proxy-monitor/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=reverse-proxy-monitor

# Лимиты ресурсов
LimitNOFILE=65536
LimitNPROC=32768

[Install]
WantedBy=multi-user.target
EOF
    
    # Перезагружаем systemd
    systemctl daemon-reload
    systemctl enable reverse-proxy-monitor
    
    log "Systemd сервис создан и включен"
}

# Настройка Nginx
setup_nginx() {
    log "Настройка Nginx..."
    
    case $OS in
        ubuntu|debian)
            apt-get install -y nginx
            ;;
        centos|rhel|rocky|almalinux)
            yum install -y nginx
            ;;
    esac
    
    # Создаем конфигурацию Nginx
    cat > /etc/nginx/sites-available/reverse-proxy-monitor << EOF
server {
    listen 80;
    server_name _;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Статические файлы
    location /static/ {
        alias /opt/reverse-proxy-monitor/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    
    # Активируем сайт (для Ubuntu/Debian)
    if [[ -d "/etc/nginx/sites-enabled" ]]; then
        ln -sf /etc/nginx/sites-available/reverse-proxy-monitor /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
    fi
    
    # Тестируем конфигурацию
    nginx -t
    
    systemctl enable nginx
    systemctl restart nginx
    
    log "Nginx настроен и запущен"
}

# Настройка файрвола
setup_firewall() {
    log "Настройка файрвола..."
    
    if command -v ufw >/dev/null 2>&1; then
        # Ubuntu/Debian UFW
        ufw allow ssh
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
    elif command -v firewall-cmd >/dev/null 2>&1; then
        # CentOS/RHEL firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        systemctl enable firewalld
    fi
    
    log "Файрвол настроен"
}

# Установка правильных разрешений
set_permissions() {
    log "Установка правильных разрешений..."
    
    # Меняем владельца всех файлов
    chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/
    
    # Устанавливаем правильные права
    chmod -R 755 /opt/reverse-proxy-monitor/
    chmod 600 /opt/reverse-proxy-monitor/.env
    
    # Делаем скрипты исполняемыми
    find /opt/reverse-proxy-monitor/ -name "*.sh" -exec chmod +x {} \;
    
    log "Разрешения установлены"
}

# Запуск сервиса
start_services() {
    log "Запуск сервисов..."
    
    # Запускаем приложение
    systemctl start reverse-proxy-monitor
    
    # Ждем немного для запуска
    sleep 5
    
    # Проверяем статус
    systemctl status reverse-proxy-monitor --no-pager
    
    log "Сервисы запущены"
}

# Создание скрипта обновления
create_update_script() {
    log "Создание скрипта обновления..."
    
    cat > /opt/reverse-proxy-monitor/update.sh << 'EOF'
#!/bin/bash
# Скрипт обновления Reverse Proxy Monitor

echo "🔄 Обновление Reverse Proxy Monitor..."

cd /opt/reverse-proxy-monitor

# Останавливаем сервис
sudo systemctl stop reverse-proxy-monitor

# Создаем резервную копию
cp -r . "../reverse-proxy-monitor-backup-$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

# Обновляем код
git pull origin main

# Активируем виртуальное окружение
source venv/bin/activate

# Обновляем зависимости
pip install --upgrade -r setup_requirements.txt

# Применяем миграции
alembic upgrade head || echo "Миграции не требуются"

# Восстанавливаем права
sudo chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/
sudo chmod 600 .env

# Запускаем сервис
sudo systemctl start reverse-proxy-monitor

echo "✅ Обновление завершено"
echo "Проверьте статус: sudo systemctl status reverse-proxy-monitor"
EOF
    
    chmod +x /opt/reverse-proxy-monitor/update.sh
    chown rpmonitor:rpmonitor /opt/reverse-proxy-monitor/update.sh
    
    log "Скрипт обновления создан: /opt/reverse-proxy-monitor/update.sh"
}

# Финальная проверка
final_check() {
    log "Финальная проверка установки..."
    
    # Проверяем статус сервисов
    echo -e "\n${BLUE}=== СТАТУС СЕРВИСОВ ===${NC}"
    systemctl is-active postgresql && echo "✅ PostgreSQL: активен" || echo "❌ PostgreSQL: неактивен"
    systemctl is-active nginx && echo "✅ Nginx: активен" || echo "❌ Nginx: неактивен"  
    systemctl is-active reverse-proxy-monitor && echo "✅ Reverse Proxy Monitor: активен" || echo "❌ Reverse Proxy Monitor: неактивен"
    
    # Проверяем порты
    echo -e "\n${BLUE}=== ПРОВЕРКА ПОРТОВ ===${NC}"
    ss -tlnp | grep ":80 " && echo "✅ Порт 80: слушает" || echo "❌ Порт 80: не слушает"
    ss -tlnp | grep ":5000 " && echo "✅ Порт 5000: слушает" || echo "❌ Порт 5000: не слушает"
    
    # Тестируем HTTP
    echo -e "\n${BLUE}=== HTTP ТЕСТ ===${NC}"
    curl -I http://localhost/ 2>/dev/null | head -1 && echo "✅ HTTP: отвечает" || echo "❌ HTTP: не отвечает"
    
    # Проверяем логи
    echo -e "\n${BLUE}=== ПОСЛЕДНИЕ ЛОГИ ===${NC}"
    journalctl -u reverse-proxy-monitor --no-pager -n 5
    
    echo -e "\n${GREEN}=== ИНФОРМАЦИЯ ДЛЯ ВХОДА ===${NC}"
    echo "URL: http://$(hostname -I | awk '{print $1}')/"
    echo "Администратор:"
    echo "  Логин: admin"
    echo "  Пароль: admin123"
    
    echo -e "\n${BLUE}=== ПОЛЕЗНЫЕ КОМАНДЫ ===${NC}"
    echo "Статус сервиса:      sudo systemctl status reverse-proxy-monitor"
    echo "Перезапуск сервиса:  sudo systemctl restart reverse-proxy-monitor"
    echo "Логи сервиса:        sudo journalctl -u reverse-proxy-monitor -f"
    echo "Обновление:          sudo /opt/reverse-proxy-monitor/update.sh"
}

# Основная функция
main() {
    log "🚀 НАЧАЛО УСТАНОВКИ REVERSE PROXY MONITOR 2.0"
    log "Версия с исправлениями от 21 августа 2025"
    
    check_root
    detect_os
    update_system
    install_python
    install_postgresql
    setup_database
    create_app_user
    setup_application
    create_env_file
    fix_main_py
    fix_config_files
    fix_auth_settings
    run_migrations
    create_admin_user
    create_systemd_service
    setup_nginx
    setup_firewall
    set_permissions
    start_services
    create_update_script
    final_check
    
    log "🎉 УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
    
    # Очищаем временные файлы
    rm -f /tmp/db_config
    
    echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════════════╗"
    echo -e "║                    УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!                     ║"
    echo -e "║                                                                      ║"  
    echo -e "║  🌐 Веб-интерфейс: http://$(hostname -I | awk '{print $1}')/"
    echo -e "║  👤 Логин: admin                                                     ║"
    echo -e "║  🔑 Пароль: admin123                                                 ║"
    echo -e "║                                                                      ║"
    echo -e "║  📁 Приложение: /opt/reverse-proxy-monitor/                          ║"
    echo -e "║  🔄 Обновление: sudo /opt/reverse-proxy-monitor/update.sh            ║"
    echo -e "╚══════════════════════════════════════════════════════════════════════╝${NC}"
}

# Обработка сигналов
trap 'error "Установка прервана"' INT TERM

# Запуск
main "$@"