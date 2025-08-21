#!/bin/bash

# Исправленный скрипт деплоя для сервера

set -e

echo "🔧 Исправление конфигурации Reverse Proxy Monitor..."

# Проверка запуска от root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Этот скрипт должен запускаться от пользователя root"
   exit 1
fi

APP_USER="rpmonitor"
INSTALL_DIR="/opt/reverse-proxy-monitor"

# Остановка сервиса
echo "⏹️ Остановка сервиса..."
systemctl stop reverse-proxy-monitor || true

# Сохранение существующих значений
if [[ -f "$INSTALL_DIR/.env" ]]; then
    DB_URL=$(grep "^DATABASE_URL=" $INSTALL_DIR/.env | cut -d'=' -f2-)
    SECRET_KEY=$(grep "^SECRET_KEY=" $INSTALL_DIR/.env | head -1 | cut -d'=' -f2-)
else
    echo "❌ Файл .env не найден!"
    exit 1
fi

# Создание правильного .env файла
echo "📝 Создание правильного .env файла..."
cat > $INSTALL_DIR/.env << 'EOF'
# Database Configuration
DATABASE_URL=placeholder_db_url

# Security
SECRET_KEY=placeholder_secret_key

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

# Замена placeholder значений на реальные
sed -i "s|placeholder_db_url|$DB_URL|g" $INSTALL_DIR/.env
sed -i "s|placeholder_secret_key|$SECRET_KEY|g" $INSTALL_DIR/.env

# Установка прав
chown $APP_USER:$APP_USER $INSTALL_DIR/.env
chmod 600 $INSTALL_DIR/.env

echo "✅ Файл .env исправлен"

# Проверка содержимого
echo "📋 Новое содержимое .env:"
cat $INSTALL_DIR/.env

# Тестирование запуска
echo "🧪 Тестирование запуска приложения..."
cd $INSTALL_DIR
if timeout 10 sudo -u $APP_USER bash -c "source venv/bin/activate && python main.py" > /tmp/test_output.log 2>&1; then
    echo "✅ Приложение запускается успешно"
else
    echo "❌ Ошибка при тестировании:"
    echo "--- Последние строки лога ---"
    tail -20 /tmp/test_output.log
    echo "--- Конец лога ---"
    exit 1
fi

# Запуск сервиса
echo "🚀 Запуск сервиса..."
systemctl start reverse-proxy-monitor
sleep 3

# Проверка статуса
echo "📊 Статус сервиса:"
systemctl status reverse-proxy-monitor --no-pager

# Проверка портов
echo "🌐 Проверка портов:"
ss -tlnp | grep :5000 || echo "Порт 5000 не найден"

echo ""
echo "✅ Деплой исправлен успешно!"
echo "🌐 Приложение должно быть доступно на http://ваш-сервер:5000"