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

# Запрос настроек
get_settings() {
    echo
    log "=== НАСТРОЙКИ ДЕПЛОЯ ==="
    
    read -p "GitHub репозиторий URL (https://github.com/username/repo.git): " REPO_URL
    if [[ -z "$REPO_URL" ]]; then
        error "URL репозитория обязателен!"
        exit 1
    fi
    
    read -p "Имя пользователя для приложения (по умолчанию: rpmonitor): " APP_USER
    APP_USER=${APP_USER:-rpmonitor}
    
    read -p "Директория установки (по умолчанию: /opt/reverse-proxy-monitor): " INSTALL_DIR
    INSTALL_DIR=${INSTALL_DIR:-/opt/reverse-proxy-monitor}
    
    read -p "Порт приложения (по умолчанию: 5000): " APP_PORT
    APP_PORT=${APP_PORT:-5000}
    
    read -p "Домен для nginx (опционально, например: monitor.example.com): " DOMAIN
    
    read -p "Настроить PostgreSQL? (y/N): " -n 1 -r SETUP_POSTGRES
    echo
    
    if [[ $SETUP_POSTGRES =~ ^[Yy]$ ]]; then
        read -p "Имя базы данных (по умолчанию: rpmonitor): " DB_NAME
        DB_NAME=${DB_NAME:-rpmonitor}
        
        read -p "Пользователь БД (по умолчанию: rpmonitor): " DB_USER
        DB_USER=${DB_USER:-rpmonitor}
        
        read -s -p "Пароль для БД: " DB_PASSWORD
        echo
        
        if [[ -z "$DB_PASSWORD" ]]; then
            error "Пароль БД обязателен!"
            exit 1
        fi
    fi
    
    echo
    log "Настройки:"
    info "Репозиторий: $REPO_URL"
    info "Пользователь: $APP_USER"
    info "Директория: $INSTALL_DIR"
    info "Порт: $APP_PORT"
    [[ -n "$DOMAIN" ]] && info "Домен: $DOMAIN"
    [[ $SETUP_POSTGRES =~ ^[Yy]$ ]] && info "PostgreSQL: Да (БД: $DB_NAME, Пользователь: $DB_USER)"
    
    echo
    read -p "Продолжить установку? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
}

# Обновление системы
update_system() {
    log "Обновление системы..."
    if [[ $USE_ROOT == true ]]; then
        apt update
        apt upgrade -y
    else
        sudo apt update
        sudo apt upgrade -y
    fi
}

# Установка системных зависимостей
install_system_deps() {
    log "Установка системных зависимостей..."
    if [[ $USE_ROOT == true ]]; then
        apt install -y \
            curl \
            wget \
            git \
            build-essential \
            software-properties-common \
            apt-transport-https \
            ca-certificates \
            gnupg \
            lsb-release \
            nginx \
            supervisor \
            htop \
            vim \
            ufw
    else
        sudo apt install -y \
            curl \
            wget \
            git \
            build-essential \
            software-properties-common \
            apt-transport-https \
            ca-certificates \
            gnupg \
            lsb-release \
            nginx \
            supervisor \
            htop \
            vim \
            ufw
    fi
}

# Установка Python 3.11
install_python() {
    log "Установка Python 3.11..."
    
    if [[ $USE_ROOT == true ]]; then
        # Добавление PPA для Python 3.11
        add-apt-repository ppa:deadsnakes/ppa -y
        apt update
        
        apt install -y \
            python3.11 \
            python3.11-dev \
            python3.11-venv \
            python3-pip
        
        # Создание симлинка
        ln -sf /usr/bin/python3.11 /usr/bin/python3
    else
        # Добавление PPA для Python 3.11
        sudo add-apt-repository ppa:deadsnakes/ppa -y
        sudo apt update
        
        sudo apt install -y \
            python3.11 \
            python3.11-dev \
            python3.11-venv \
            python3-pip
        
        # Создание симлинка
        sudo ln -sf /usr/bin/python3.11 /usr/bin/python3
    fi
}

# Установка PostgreSQL
install_postgresql() {
    if [[ $SETUP_POSTGRES =~ ^[Yy]$ ]]; then
        log "Установка PostgreSQL..."
        if [[ $USE_ROOT == true ]]; then
            apt install -y postgresql postgresql-contrib
        else
            sudo apt install -y postgresql postgresql-contrib
        fi
        
        log "Настройка базы данных..."
        sudo -u postgres psql << EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
\q
EOF
        
        log "PostgreSQL настроен. База: $DB_NAME, Пользователь: $DB_USER"
    fi
}

# Создание пользователя приложения
create_app_user() {
    if ! id "$APP_USER" &>/dev/null; then
        log "Создание пользователя $APP_USER..."
        if [[ $USE_ROOT == true ]]; then
            useradd -r -s /bin/bash -d $INSTALL_DIR $APP_USER
        else
            sudo useradd -r -s /bin/bash -d $INSTALL_DIR $APP_USER
        fi
    else
        info "Пользователь $APP_USER уже существует"
    fi
}

# Клонирование репозитория
clone_repository() {
    log "Клонирование репозитория..."
    
    if [[ -d "$INSTALL_DIR" ]]; then
        warn "Директория $INSTALL_DIR уже существует. Удаляем..."
        rm -rf $INSTALL_DIR
    fi
    
    mkdir -p $INSTALL_DIR
    git clone $REPO_URL $INSTALL_DIR
    chown -R $APP_USER:$APP_USER $INSTALL_DIR
}

# Установка Python зависимостей
install_python_deps() {
    log "Установка Python зависимостей..."
    
    sudo -u $APP_USER bash << EOF
cd $INSTALL_DIR
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Попытка установить из requirements.txt или setup_requirements.txt
if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt
elif [[ -f "setup_requirements.txt" ]]; then
    pip install -r setup_requirements.txt
else
    # Установка базовых зависимостей
    pip install \
        fastapi==0.104.1 \
        "uvicorn[standard]==0.24.0" \
        sqlalchemy==2.0.23 \
        alembic==1.12.1 \
        psycopg2-binary==2.9.9 \
        pydantic==2.5.0 \
        pydantic-settings==2.1.0 \
        typer==0.9.0 \
        "passlib[bcrypt]==1.7.4" \
        "python-jose[cryptography]==3.3.0" \
        python-multipart==0.0.6 \
        httpx==0.25.2 \
        paramiko==3.3.1 \
        dnspython==2.4.2 \
        cryptography==41.0.7 \
        apscheduler==3.10.4 \
        jinja2==3.1.2 \
        aiofiles==23.2.1
fi
EOF
}

# Создание файла окружения
create_env_file() {
    log "Создание файла окружения..."
    
    if [[ $USE_ROOT == true ]]; then
        su $APP_USER -c "cat > $INSTALL_DIR/.env" << EOF
    else
        sudo -u $APP_USER tee $INSTALL_DIR/.env > /dev/null << EOF
    fi
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

    chmod 600 $INSTALL_DIR/.env
}

# Инициализация базы данных
init_database() {
    if [[ $SETUP_POSTGRES =~ ^[Yy]$ ]]; then
        log "Инициализация базы данных..."
        
        if [[ $USE_ROOT == true ]]; then
            su -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py init-db 2>/dev/null || echo 'База данных уже инициализирована или файл manage.py не найден'" $APP_USER
        else
            sudo -u $APP_USER bash << EOF
cd $INSTALL_DIR
source venv/bin/activate
python manage.py init-db 2>/dev/null || echo "База данных уже инициализирована или файл manage.py не найден"
EOF
        fi
    fi
}

# Создание systemd сервиса
create_systemd_service() {
    log "Создание systemd сервиса..."
    
    tee /etc/systemd/system/reverse-proxy-monitor.service > /dev/null << EOF
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
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=3
KillMode=mixed
TimeoutStopSec=5

# Security
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable reverse-proxy-monitor
}

# Настройка Nginx
configure_nginx() {
    log "Настройка Nginx..."
    
    if [[ -n "$DOMAIN" ]]; then
        tee /etc/nginx/sites-available/reverse-proxy-monitor > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        proxy_buffering off;
    }
    
    location /static/ {
        alias $INSTALL_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
        
        ln -sf /etc/nginx/sites-available/reverse-proxy-monitor /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
        
        log "Nginx настроен для домена: $DOMAIN"
        info "Для SSL сертификата используйте: certbot --nginx -d $DOMAIN"
    else
        warn "Домен не указан. Настройте Nginx вручную или используйте IP:$APP_PORT"
    fi
    
    nginx -t
    systemctl restart nginx
}

# Настройка файрвола
configure_firewall() {
    log "Настройка файрвола..."
    
    ufw --force enable
    ufw default deny incoming
    ufw default allow outgoing
    
    # SSH
    ufw allow ssh
    
    # HTTP/HTTPS
    ufw allow 80
    ufw allow 443
    
    # Порт приложения (если нет домена)
    if [[ -z "$DOMAIN" ]]; then
        ufw allow $APP_PORT
    fi
    
    ufw --force reload
}

# Установка логротации
setup_log_rotation() {
    log "Настройка ротации логов..."
    
    tee /etc/logrotate.d/reverse-proxy-monitor > /dev/null << EOF
$INSTALL_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 $APP_USER $APP_USER
    postrotate
        systemctl reload reverse-proxy-monitor
    endscript
}
EOF

    # Создание директории логов
    mkdir -p $INSTALL_DIR/logs
    chown $APP_USER:$APP_USER $INSTALL_DIR/logs
}

# Запуск сервисов
start_services() {
    log "Запуск сервисов..."
    
    systemctl start reverse-proxy-monitor
    systemctl restart nginx
    
    sleep 5
    
    if systemctl is-active --quiet reverse-proxy-monitor; then
        log "✅ Сервис reverse-proxy-monitor запущен успешно"
    else
        error "❌ Ошибка запуска сервиса reverse-proxy-monitor"
        journalctl -u reverse-proxy-monitor --no-pager -n 20
    fi
}

# Создание скрипта обновления
create_update_script() {
    log "Создание скрипта обновления..."
    
    tee $INSTALL_DIR/update.sh > /dev/null << 'EOF'
#!/bin/bash
# Скрипт обновления приложения

set -e

log() {
    echo -e "\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\033[0m"
}

error() {
    echo -e "\033[0;31m[ERROR] $1\033[0m"
}

INSTALL_DIR=$(dirname "$(readlink -f "$0")")
cd $INSTALL_DIR

log "Создание резервной копии..."
cp -r $INSTALL_DIR $INSTALL_DIR.backup.$(date +%Y%m%d_%H%M%S)

log "Получение обновлений из Git..."
git fetch origin
git reset --hard origin/main

log "Обновление зависимостей..."
source venv/bin/activate
pip install --upgrade -r requirements.txt

log "Применение миграций БД..."
python manage.py migrate 2>/dev/null || echo "Миграции не требуются"

log "Перезапуск сервиса..."
sudo systemctl restart reverse-proxy-monitor

log "✅ Обновление завершено успешно!"
EOF

    chmod +x $INSTALL_DIR/update.sh
    chown $APP_USER:$APP_USER $INSTALL_DIR/update.sh
}

# Финальная информация
show_final_info() {
    echo
    log "🎉 УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
    echo
    info "=== ИНФОРМАЦИЯ О СИСТЕМЕ ==="
    info "Директория приложения: $INSTALL_DIR"
    info "Пользователь: $APP_USER"
    info "Порт приложения: $APP_PORT"
    [[ -n "$DOMAIN" ]] && info "Домен: http://$DOMAIN" || info "Доступ: http://$(curl -s ifconfig.me):$APP_PORT"
    [[ $SETUP_POSTGRES =~ ^[Yy]$ ]] && info "База данных: $DB_NAME (пользователь: $DB_USER)"
    echo
    info "=== ПОЛЕЗНЫЕ КОМАНДЫ ==="
    info "Статус сервиса:     systemctl status reverse-proxy-monitor"
    info "Логи сервиса:       journalctl -u reverse-proxy-monitor -f"
    info "Перезапуск:         systemctl restart reverse-proxy-monitor"
    info "Обновление:         su -c '$INSTALL_DIR/update.sh' $APP_USER"
    info "Конфигурация:       $INSTALL_DIR/.env"
    echo
    info "=== ПЕРВЫЙ ВХОД ==="
    info "Логин: admin"
    info "Пароль: admin123"
    info "⚠️  Обязательно смените пароль после первого входа!"
    echo
    warn "Не забудьте:"
    warn "1. Настроить Telegram бота (если нужно)"
    warn "2. Настроить SSL сертификат: apt install certbot python3-certbot-nginx && certbot --nginx -d $DOMAIN"
    warn "3. Изменить пароль администратора"
    echo
}

# Основная функция
main() {
    echo
    log "🚀 АВТОМАТИЧЕСКИЙ ДЕПЛОЙ REVERSE PROXY & MONITOR"
    log "Для Ubuntu 22.04"
    echo
    
    check_root
    check_ubuntu
    get_settings
    
    log "Начинаем установку..."
    
    update_system
    install_system_deps
    install_python
    install_postgresql
    create_app_user
    clone_repository
    install_python_deps
    create_env_file
    init_database
    create_systemd_service
    configure_nginx
    configure_firewall
    setup_log_rotation
    start_services
    create_update_script
    
    show_final_info
}

# Обработка сигналов
trap 'error "Установка прервана!"; exit 1' INT TERM

# Запуск
main "$@"