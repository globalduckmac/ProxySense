#!/bin/bash

# Скрипт исправления деплоя для Reverse Proxy Monitor

set -e

APP_USER="rpmonitor"
INSTALL_DIR="/opt/reverse-proxy-monitor"

echo "Исправление конфигурации..."

# Остановка сервиса
systemctl stop reverse-proxy-monitor || true
systemctl disable reverse-proxy-monitor || true

# Получение существующих значений из старого .env
OLD_DB_URL=$(grep "DATABASE_URL=" $INSTALL_DIR/.env | cut -d'=' -f2- || echo "")
OLD_SECRET=$(grep "SECRET_KEY=" $INSTALL_DIR/.env | cut -d'=' -f2- || echo "")

# Создание правильного .env файла
cat > $INSTALL_DIR/.env << EOF
# Database Configuration
DATABASE_URL=$OLD_DB_URL

# Security
SECRET_KEY=$OLD_SECRET

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

# Установка прав
chown $APP_USER:$APP_USER $INSTALL_DIR/.env
chmod 600 $INSTALL_DIR/.env

# Создание правильного systemd сервиса
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

# Проверка установки зависимостей
echo "Проверка зависимостей..."
if [[ ! -f "$INSTALL_DIR/main.py" ]]; then
    echo "ОШИБКА: Файл main.py не найден!"
    echo "Проверьте структуру проекта в $INSTALL_DIR"
    exit 1
fi

# Инициализация базы данных
echo "Инициализация базы данных..."
cd $INSTALL_DIR
sudo -u $APP_USER bash -c "source venv/bin/activate && python -c 'from backend.database import init_db; init_db()'" || true

# Перезапуск daemon и включение сервиса
systemctl daemon-reload
systemctl enable reverse-proxy-monitor

echo "Тестирование запуска..."
if sudo -u $APP_USER bash -c "cd $INSTALL_DIR && source venv/bin/activate && timeout 10 python main.py" > /tmp/test.log 2>&1; then
    echo "✅ Приложение запускается успешно"
else
    echo "❌ Ошибка при тестировании:"
    cat /tmp/test.log
    exit 1
fi

# Запуск сервиса
systemctl start reverse-proxy-monitor
sleep 3
systemctl status reverse-proxy-monitor --no-pager

echo "✅ Деплой исправлен успешно!"
echo "🌐 Приложение должно быть доступно на порту 5000"