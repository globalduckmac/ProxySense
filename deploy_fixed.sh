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
    
    # Переходим в директорию приложения
    cd /opt/reverse-proxy-monitor
    
    # Клонируем или обновляем репозиторий
    if [[ ! -d ".git" ]]; then
        log "Клонирование репозитория..."
        git clone https://github.com/globalduckmac/ProxySense.git .
    else
        log "Обновление существующего репозитория..."
        git pull origin main
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
    
    # Создаем скрипт исправления
    cat > fix_auth_issue.py << 'EOF'
import os
import re

# Исправляем backend/auth.py для работы с reverse proxy
auth_file = "backend/auth.py"

if os.path.exists(auth_file):
    with open(auth_file, 'r') as f:
        content = f.read()
    
    # Заменяем настройки cookie на правильные для reverse proxy
    content = re.sub(
        r'response\.set_cookie\([^)]*secure=True[^)]*\)',
        lambda m: m.group(0).replace('secure=True', 'secure=False'),
        content
    )
    
    content = re.sub(
        r'response\.set_cookie\([^)]*samesite=["\'][^"\']*["\'][^)]*\)',
        lambda m: re.sub(r'samesite=["\'][^"\']*["\']', 'samesite="lax"', m.group(0)),
        content
    )
    
    # Если нет настроек cookie, добавляем правильные
    if 'set_cookie(' in content and 'secure=' not in content:
        content = content.replace(
            'response.set_cookie(',
            'response.set_cookie('
        )
        # Находим все вызовы set_cookie и добавляем параметры
        content = re.sub(
            r'response\.set_cookie\(\s*"access_token"[^)]*\)',
            lambda m: m.group(0)[:-1] + ', secure=False, samesite="lax")',
            content
        )
    
    with open(auth_file, 'w') as f:
        f.write(content)
    
    print("✅ backend/auth.py исправлен для работы с reverse proxy")
else:
    print("❌ backend/auth.py не найден")
EOF
    
    python3 fix_auth_issue.py
    rm fix_auth_issue.py
}

# Исправление настроек пула БД
fix_database_pool() {
    log "Исправление настроек пула базы данных..."
    
    cat > fix_database_pool.py << 'EOF'
import os
import re

# Исправляем backend/database.py или backend/app.py
files_to_check = ["backend/database.py", "backend/app.py", "backend/models.py"]

for file_path in files_to_check:
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Ищем настройки engine и увеличиваем пул
        if 'create_engine' in content:
            # Заменяем настройки пула
            content = re.sub(
                r'pool_size=\d+',
                'pool_size=20',
                content
            )
            content = re.sub(
                r'max_overflow=\d+', 
                'max_overflow=30',
                content
            )
            content = re.sub(
                r'pool_timeout=\d+',
                'pool_timeout=60',
                content
            )
            
            # Если настроек нет, добавляем их
            if 'pool_size=' not in content and 'create_engine(' in content:
                content = re.sub(
                    r'create_engine\([^)]+\)',
                    lambda m: m.group(0)[:-1] + ', pool_size=20, max_overflow=30, pool_timeout=60)',
                    content
                )
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            print(f"✅ {file_path} - настройки пула БД обновлены")
            break
EOF
    
    python3 fix_database_pool.py
    rm fix_database_pool.py
}

# Применение миграций БД
run_migrations() {
    log "Применение миграций базы данных..."
    
    source venv/bin/activate
    
    # Инициализируем Alembic если нужно
    if [[ ! -d "migrations" ]]; then
        alembic init migrations
    fi
    
    # Применяем миграции
    alembic upgrade head || {
        warn "Не удалось применить миграции Alembic, создаем таблицы через SQLAlchemy"
        python3 -c "
from backend.app import app
from backend.database import Base, engine
import backend.models
with app.app_context():
    Base.metadata.create_all(engine)
print('Таблицы созданы')
"
    }
}

# Создание администратора
create_admin_user() {
    log "Создание администратора..."
    
    source venv/bin/activate
    
    cat > create_admin.py << 'EOF'
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from backend.database import get_db_session
from backend.models import User
from backend.auth import get_password_hash
from sqlalchemy.orm import Session

async def create_admin():
    # Получаем сессию БД
    db_gen = get_db_session()
    db = next(db_gen)
    
    try:
        # Проверяем есть ли уже admin
        existing_admin = db.query(User).filter(User.username == "admin").first()
        
        if existing_admin:
            print("✅ Администратор admin уже существует")
            return
        
        # Создаем админа
        admin_user = User(
            username="admin",
            email="admin@example.com", 
            password_hash=get_password_hash("admin123"),
            is_admin=True,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("✅ Администратор создан:")
        print("   Логин: admin")
        print("   Пароль: admin123")
        
    except Exception as e:
        print(f"❌ Ошибка создания администратора: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(create_admin())
EOF
    
    python3 create_admin.py
    rm create_admin.py
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
    fix_auth_settings  
    fix_database_pool
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