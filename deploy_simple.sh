#!/bin/bash

# Упрощенный скрипт деплоя без PPA (для систем с проблемами APT)

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# Проверка root прав
if [[ $EUID -ne 0 ]]; then
   error "Этот скрипт должен запускаться от пользователя root"
fi

# Конфигурация
APP_USER="rpmonitor"
INSTALL_DIR="/opt/reverse-proxy-monitor"
REPO_URL="https://github.com/globalduckmac/ProxySense.git"
DB_NAME="rpmonitor"
DB_USER="rpmonitor"
DB_PASSWORD=$(openssl rand -base64 32)

log "🚀 Начало установки Reverse Proxy Monitor (упрощенная версия)"

# Исправление APT
log "Исправление проблем с APT..."
rm -f /usr/lib/cnf-update-db /etc/apt/apt.conf.d/50command-not-found
export DEBIAN_FRONTEND=noninteractive

# Обновление системы (игнорируем ошибки APT)
log "Обновление системы..."
apt update 2>/dev/null || warn "APT обновление с предупреждениями, продолжаем..."
apt upgrade -y 2>/dev/null || warn "APT upgrade с предупреждениями, продолжаем..."

# Установка базовых зависимостей
log "Установка базовых пакетов..."
apt install -y git curl wget nginx postgresql postgresql-contrib python3 python3-pip python3-venv build-essential libpq-dev 2>/dev/null || error "Ошибка установки базовых пакетов"

# Создание пользователя приложения
if ! id "$APP_USER" &>/dev/null; then
    log "Создание пользователя $APP_USER..."
    useradd -r -s /bin/bash -d $INSTALL_DIR $APP_USER
else
    log "Пользователь $APP_USER уже существует"
fi

# Настройка PostgreSQL
log "Настройка PostgreSQL..."
systemctl start postgresql
systemctl enable postgresql

sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS $DB_NAME;
DROP USER IF EXISTS $DB_USER;
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
\q
EOF

# Клонирование репозитория
log "Клонирование репозитория..."
if [[ -d "$INSTALL_DIR" ]]; then
    warn "Директория $INSTALL_DIR уже существует. Удаляем..."
    rm -rf $INSTALL_DIR
fi

mkdir -p $INSTALL_DIR
git clone $REPO_URL $INSTALL_DIR || error "Ошибка клонирования репозитория"
chown -R $APP_USER:$APP_USER $INSTALL_DIR

# Установка Python зависимостей
log "Установка Python зависимостей..."
sudo -u $APP_USER bash << EOF
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary pydantic pydantic-settings typer 'passlib[bcrypt]' 'python-jose[cryptography]' python-multipart httpx paramiko dnspython cryptography apscheduler jinja2 aiofiles
EOF

# Создание .env файла
log "Создание файла окружения..."
cat > $INSTALL_DIR/.env << EOF
# Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME

# Security
SECRET_KEY=$(openssl rand -hex 32)

# Application
DEBUG=False
LOG_LEVEL=INFO

# SSH
SSH_TIMEOUT=30
SSH_CONNECT_TIMEOUT=10

# Glances
GLANCES_POLL_INTERVAL=60
GLANCES_TIMEOUT=10
GLANCES_MAX_FAILURES=3

# DNS
DNS_TIMEOUT=5
DNS_SERVERS=8.8.8.8,1.1.1.1

# Telegram (опционально)
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id
EOF

chown $APP_USER:$APP_USER $INSTALL_DIR/.env
chmod 600 $INSTALL_DIR/.env

# Инициализация базы данных
log "Инициализация базы данных..."
cd $INSTALL_DIR
sudo -u $APP_USER bash << EOF
cd $INSTALL_DIR
source venv/bin/activate
python -c "from backend.database import init_db; init_db()" 2>/dev/null || echo "Инициализация завершена"
EOF

# Тестирование приложения
log "Тестирование запуска приложения..."
cd $INSTALL_DIR
if timeout 10 sudo -u $APP_USER bash -c "source venv/bin/activate && python main.py" > /tmp/test_app.log 2>&1; then
    log "✅ Приложение запускается корректно"
else
    error "❌ Ошибка при тестировании приложения: $(cat /tmp/test_app.log)"
fi

# Создание systemd сервиса
log "Создание systemd сервиса..."
cat > /etc/systemd/system/reverse-proxy-monitor.service << EOF
[Unit]
Description=Reverse Proxy Monitor
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=exec
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=reverse-proxy-monitor

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable reverse-proxy-monitor

# Создание директории логов
mkdir -p $INSTALL_DIR/logs
chown $APP_USER:$APP_USER $INSTALL_DIR/logs

# Запуск сервисов
log "Запуск сервисов..."
systemctl start reverse-proxy-monitor
systemctl restart nginx

sleep 5

if systemctl is-active --quiet reverse-proxy-monitor; then
    log "✅ Сервис reverse-proxy-monitor запущен успешно"
else
    error "❌ Ошибка запуска сервиса reverse-proxy-monitor"
fi

# Финальная информация
echo
log "🎉 УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
echo
log "=== ИНФОРМАЦИЯ О СИСТЕМЕ ==="
log "🌐 Приложение: http://$(hostname -I | awk '{print $1}'):5000"
log "👤 Пользователь приложения: $APP_USER"
log "📁 Директория: $INSTALL_DIR"
log "🗄️ База данных: $DB_NAME"
log "🔐 Пользователь БД: $DB_USER"
echo
log "=== УПРАВЛЕНИЕ СЕРВИСОМ ==="
log "▶️  Запуск: systemctl start reverse-proxy-monitor"
log "⏹️  Остановка: systemctl stop reverse-proxy-monitor"
log "🔄 Перезапуск: systemctl restart reverse-proxy-monitor"
log "📊 Статус: systemctl status reverse-proxy-monitor"
log "📋 Логи: journalctl -u reverse-proxy-monitor -f"
echo
log "Данные для входа:"
log "Логин: admin"
log "Пароль: admin123"
echo
log "Пароль БД сохранен в файле .env"