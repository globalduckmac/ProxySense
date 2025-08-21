#!/bin/bash

# Автоматический скрипт деплоя для Reverse Proxy & Monitor
# Для Ubuntu 22.04

set -e  # Остановить выполнение при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Проверка прав root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        warn "Запуск от root пользователя. Будет создан отдельный пользователь для приложения."
        USE_ROOT=true
    else
        USE_ROOT=false
    fi
}

# Проверка Ubuntu версии
check_ubuntu() {
    if ! grep -q "Ubuntu 22" /etc/os-release; then
        warn "Этот скрипт предназначен для Ubuntu 22.04. Ваша версия может отличаться."
        read -p "Продолжить? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Настройка переменных
setup_variables() {
    # Основные переменные
    APP_USER="rpmonitor"
    INSTALL_DIR="/opt/reverse-proxy-monitor"
    APP_PORT=5000
    REPO_URL="https://github.com/globalduckmac/ProxySense.git"
    
    # Настройки PostgreSQL
    DB_NAME="rpmonitor"
    DB_USER="rpmonitor"
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Настройки домена (опционально)
    read -p "Введите домен для приложения (или Enter для пропуска): " DOMAIN
    if [[ -n "$DOMAIN" ]]; then
        SETUP_NGINX=y
    else
        SETUP_NGINX=n
    fi
    
    # Настройка PostgreSQL
    read -p "Установить и настроить PostgreSQL? (Y/n): " SETUP_POSTGRES
    SETUP_POSTGRES=${SETUP_POSTGRES:-Y}
}

# Обновление системы
update_system() {
    log "Обновление системы..."
    apt update && apt upgrade -y
}

# Установка системных зависимостей
install_dependencies() {
    log "Установка системных зависимостей..."
    apt install -y \
        curl \
        wget \
        git \
        build-essential \
        software-properties-common \
        nginx \
        ufw \
        logrotate \
        supervisor \
        htop \
        nano \
        unzip \
        openssl
}

# Установка Python 3.11
install_python() {
    log "Установка Python 3.11..."
    add-apt-repository ppa:deadsnakes/ppa -y
    apt update
    apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
}

# Установка PostgreSQL
install_postgresql() {
    if [[ $SETUP_POSTGRES =~ ^[Yy]$ ]]; then
        log "Установка PostgreSQL..."
        apt install -y postgresql postgresql-contrib
        systemctl start postgresql
        systemctl enable postgresql
        
        log "Настройка базы данных..."
        sudo -u postgres createuser $DB_USER || true
        sudo -u postgres createdb $DB_NAME -O $DB_USER || true
        sudo -u postgres psql -c "ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';" || true
    fi
}

# Создание пользователя приложения
create_app_user() {
    log "Создание пользователя приложения..."
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash $APP_USER
        usermod -aG www-data $APP_USER
    fi
}

# Создание директорий
create_directories() {
    log "Создание директорий..."
    mkdir -p $INSTALL_DIR
    mkdir -p /var/log/reverse-proxy-monitor
    chown $APP_USER:$APP_USER $INSTALL_DIR
    chown $APP_USER:$APP_USER /var/log/reverse-proxy-monitor
}

# Клонирование репозитория
clone_repository() {
    log "Клонирование репозитория..."
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        cd $INSTALL_DIR
        if [[ $USE_ROOT == true ]]; then
            su $APP_USER -c "git pull origin main"
        else
            sudo -u $APP_USER git pull origin main
        fi
    else
        if [[ $USE_ROOT == true ]]; then
            su $APP_USER -c "git clone $REPO_URL $INSTALL_DIR"
        else
            sudo -u $APP_USER git clone $REPO_URL $INSTALL_DIR
        fi
    fi
    
    chown -R $APP_USER:$APP_USER $INSTALL_DIR
}

# Установка Python зависимостей
install_python_deps() {
    log "Установка Python зависимостей..."
    
    if [[ $USE_ROOT == true ]]; then
        su $APP_USER -c "cd $INSTALL_DIR && python3.11 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary pydantic pydantic-settings typer 'passlib[bcrypt]' 'python-jose[cryptography]' python-multipart httpx paramiko dnspython cryptography apscheduler jinja2 aiofiles"
    else
        sudo -u $APP_USER bash -c "cd $INSTALL_DIR && python3.11 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary pydantic pydantic-settings typer 'passlib[bcrypt]' 'python-jose[cryptography]' python-multipart httpx paramiko dnspython cryptography apscheduler jinja2 aiofiles"
    fi
}

# Создание файла окружения
create_env_file() {
    log "Создание файла окружения..."
    
    cat > $INSTALL_DIR/.env << EOF
# Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME

# Security
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Application
DEBUG=False
HOST=0.0.0.0
PORT=$APP_PORT

# Telegram (опционально)
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id

# Email (опционально)
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=your_app_password
EOF

    chown $APP_USER:$APP_USER $INSTALL_DIR/.env
    chmod 600 $INSTALL_DIR/.env
}

# Инициализация базы данных
init_database() {
    if [[ $SETUP_POSTGRES =~ ^[Yy]$ ]]; then
        log "Инициализация базы данных..."
        
        if [[ $USE_ROOT == true ]]; then
            su -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py init-db 2>/dev/null || echo 'База данных уже инициализирована или файл manage.py не найден'" $APP_USER
        else
            sudo -u $APP_USER bash -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py init-db 2>/dev/null || echo 'База данных уже инициализирована или файл manage.py не найден'"
        fi
    fi
}

# Создание systemd сервиса
create_systemd_service() {
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
}

# Настройка Nginx
setup_nginx() {
    if [[ $SETUP_NGINX =~ ^[Yy]$ ]] && [[ -n "$DOMAIN" ]]; then
        log "Настройка Nginx..."
        
        cat > /etc/nginx/sites-available/reverse-proxy-monitor << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
    }
}
EOF

        ln -sf /etc/nginx/sites-available/reverse-proxy-monitor /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
        nginx -t && systemctl reload nginx
    fi
}

# Настройка UFW
setup_firewall() {
    log "Настройка файрвола..."
    ufw --force enable
    ufw allow ssh
    ufw allow 'Nginx Full'
    if [[ $SETUP_NGINX != "y" ]]; then
        ufw allow $APP_PORT
    fi
}

# Создание скрипта обновления
create_update_script() {
    log "Создание скрипта обновления..."
    
    cat > $INSTALL_DIR/update.sh << 'EOF'
#!/bin/bash
set -e

INSTALL_DIR="/opt/reverse-proxy-monitor"
APP_USER="rpmonitor"

echo "Создание резервной копии..."
cp -r $INSTALL_DIR /opt/reverse-proxy-monitor-backup-$(date +%Y%m%d-%H%M%S)

echo "Остановка сервиса..."
systemctl stop reverse-proxy-monitor

echo "Обновление кода..."
cd $INSTALL_DIR
sudo -u $APP_USER git pull origin main

echo "Обновление зависимостей..."
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip && pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary pydantic pydantic-settings typer 'passlib[bcrypt]' 'python-jose[cryptography]' python-multipart httpx paramiko dnspython cryptography apscheduler jinja2 aiofiles"

echo "Применение миграций..."
sudo -u $APP_USER bash -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py migrate 2>/dev/null || echo 'Миграции не найдены'"

echo "Запуск сервиса..."
systemctl start reverse-proxy-monitor

echo "Обновление завершено!"
EOF

    chmod +x $INSTALL_DIR/update.sh
    chown $APP_USER:$APP_USER $INSTALL_DIR/update.sh
}

# Настройка логирования
setup_logging() {
    log "Настройка ротации логов..."
    
    cat > /etc/logrotate.d/reverse-proxy-monitor << EOF
/var/log/reverse-proxy-monitor/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        systemctl reload reverse-proxy-monitor > /dev/null 2>&1 || true
    endscript
}
EOF
}

# Запуск сервиса
start_services() {
    log "Запуск сервисов..."
    systemctl start reverse-proxy-monitor
    systemctl start nginx
    systemctl status reverse-proxy-monitor --no-pager -l
}

# Показать итоговую информацию
show_final_info() {
    log "Установка завершена!"
    echo
    echo "=================================="
    echo "    REVERSE PROXY & MONITOR"
    echo "=================================="
    echo
    info "Доступ к приложению:"
    if [[ -n "$DOMAIN" ]]; then
        info "  URL: http://$DOMAIN"
    else
        info "  URL: http://$(hostname -I | awk '{print $1}'):$APP_PORT"
    fi
    echo
    info "Учетные данные по умолчанию:"
    info "  Логин: admin"
    info "  Пароль: admin123"
    echo
    warn "ВАЖНО: Обязательно смените пароль после первого входа!"
    echo
    info "Управление сервисом:"
    info "  Статус: systemctl status reverse-proxy-monitor"
    info "  Остановка: systemctl stop reverse-proxy-monitor"
    info "  Запуск: systemctl start reverse-proxy-monitor"
    info "  Логи: journalctl -u reverse-proxy-monitor -f"
    echo
    info "Файлы конфигурации:"
    info "  Приложение: $INSTALL_DIR"
    info "  Конфигурация: $INSTALL_DIR/.env"
    info "  Логи: /var/log/reverse-proxy-monitor/"
    echo
    if [[ $SETUP_POSTGRES =~ ^[Yy]$ ]]; then
        info "База данных PostgreSQL:"
        info "  Имя БД: $DB_NAME"
        info "  Пользователь: $DB_USER"
        info "  Пароль: $DB_PASSWORD"
        echo
    fi
    if [[ -n "$DOMAIN" ]]; then
        info "Для настройки SSL выполните:"
        info "  apt install certbot python3-certbot-nginx"
        info "  certbot --nginx -d $DOMAIN"
        echo
    fi
    info "Скрипт обновления: $INSTALL_DIR/update.sh"
    echo
    echo "=================================="
}

# Основная функция
main() {
    log "Начинаем установку Reverse Proxy & Monitor..."
    
    check_root
    check_ubuntu
    setup_variables
    
    update_system
    install_dependencies
    install_python
    install_postgresql
    create_app_user
    create_directories
    clone_repository
    install_python_deps
    create_env_file
    init_database
    create_systemd_service
    setup_nginx
    setup_firewall
    create_update_script
    setup_logging
    start_services
    show_final_info
}

# Обработка сигналов
trap 'error "Установка прервана!"; exit 1' INT TERM

# Запуск
main "$@"