#!/bin/bash

###############################################################################
# ПРОСТОЙ СКРИПТ РАЗВЕРТЫВАНИЯ REVERSE PROXY MONITOR
# Упрощенная версия с основными исправлениями
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
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

# Проверка root
if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
fi

log "🚀 Быстрое развертывание с исправлениями..."

# Обновление системы
log "Обновление системы..."
apt-get update -y
apt-get install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx git

# Настройка БД
log "Настройка PostgreSQL..."
systemctl start postgresql
systemctl enable postgresql

# Создание БД
DB_PASSWORD=$(openssl rand -base64 16)
sudo -u postgres psql <<EOF
CREATE DATABASE reverse_proxy_monitor;
CREATE USER rpmonitor WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE reverse_proxy_monitor TO rpmonitor;
ALTER USER rpmonitor CREATEDB;
\q
EOF

# Создание пользователя приложения
log "Создание пользователя приложения..."
if ! id "rpmonitor" &>/dev/null; then
    useradd --system --shell /bin/bash --home /opt/reverse-proxy-monitor --create-home rpmonitor
fi

# Клонирование приложения
log "Клонирование приложения..."
cd /opt/reverse-proxy-monitor
if [[ ! -d ".git" ]]; then
    git clone https://github.com/globalduckmac/ProxySense.git .
fi

# Создание виртуального окружения
log "Настройка Python окружения..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r setup_requirements.txt

# Создание .env файла (ИСПРАВЛЕННАЯ ВЕРСИЯ)
log "Создание .env файла..."
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

cat > .env << EOF
DATABASE_URL=postgresql://rpmonitor:${DB_PASSWORD}@localhost:5432/reverse_proxy_monitor
JWT_SECRET_KEY=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
DEBUG=false
ENVIRONMENT=production

# ИСПРАВЛЕНИЯ:
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=60
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

DNS_SERVERS=8.8.8.8,1.1.1.1
SERVER_CHECK_INTERVAL=300
NS_CHECK_INTERVAL=3600
ALERT_COOLDOWN=1800
EOF

# Исправление main.py (КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ)
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

# Исправление настроек аутентификации
log "Исправление настроек cookie..."
if [[ -f "backend/auth.py" ]]; then
    sed -i 's/secure=True/secure=False/g' backend/auth.py
    sed -i 's/samesite="strict"/samesite="lax"/g' backend/auth.py
    sed -i 's/samesite="Strict"/samesite="lax"/g' backend/auth.py
fi

# Исправление настроек БД пула
log "Исправление настроек пула БД..."
find backend/ -name "*.py" -exec sed -i 's/pool_size=5/pool_size=20/g' {} \;
find backend/ -name "*.py" -exec sed -i 's/max_overflow=10/max_overflow=30/g' {} \;

# Инициализация БД
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

# Создание админа
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
            is_admin=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print('✅ Администратор создан: admin/admin123')
    else:
        print('✅ Администратор уже существует')
    
    db.close()
except Exception as e:
    print(f'Ошибка создания админа: {e}')
"

# Создание systemd сервиса
log "Создание сервиса..."
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

[Install]
WantedBy=multi-user.target
EOF

# Настройка Nginx
log "Настройка Nginx..."
cat > /etc/nginx/sites-available/reverse-proxy-monitor << EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /opt/reverse-proxy-monitor/static/;
    }
}
EOF

# Активация сайта
ln -sf /etc/nginx/sites-available/reverse-proxy-monitor /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t

# Установка прав доступа
log "Установка прав доступа..."
chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/
chmod 600 .env
chmod +x main.py

# Запуск сервисов
log "Запуск сервисов..."
systemctl daemon-reload
systemctl enable reverse-proxy-monitor
systemctl enable nginx
systemctl restart nginx
systemctl start reverse-proxy-monitor

# Настройка файрвола
log "Настройка файрвола..."
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Проверка
log "Финальная проверка..."
sleep 5

echo -e "\n${GREEN}=== СТАТУС СЕРВИСОВ ===${NC}"
systemctl is-active postgresql && echo "✅ PostgreSQL: работает" || echo "❌ PostgreSQL: не работает"
systemctl is-active nginx && echo "✅ Nginx: работает" || echo "❌ Nginx: не работает"
systemctl is-active reverse-proxy-monitor && echo "✅ Приложение: работает" || echo "❌ Приложение: не работает"

echo -e "\n${GREEN}=== ТЕСТ ПОДКЛЮЧЕНИЯ ===${NC}"
curl -I http://localhost/ 2>/dev/null | head -1 && echo "✅ HTTP: работает" || echo "❌ HTTP: не работает"

echo -e "\n${GREEN}=== ИНФОРМАЦИЯ ДЛЯ ВХОДА ===${NC}"
echo "🌐 URL: http://$(hostname -I | awk '{print $1}')/"
echo "👤 Логин: admin"
echo "🔑 Пароль: admin123"

echo -e "\n${GREEN}=== ПОЛЕЗНЫЕ КОМАНДЫ ===${NC}"
echo "Проверить статус:      sudo systemctl status reverse-proxy-monitor"
echo "Перезапустить:         sudo systemctl restart reverse-proxy-monitor"
echo "Посмотреть логи:       sudo journalctl -u reverse-proxy-monitor -f"

log "🎉 УСТАНОВКА ЗАВЕРШЕНА!"

# Показать последние логи
echo -e "\n${GREEN}=== ПОСЛЕДНИЕ ЛОГИ ===${NC}"
journalctl -u reverse-proxy-monitor --no-pager -n 10