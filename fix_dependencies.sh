#!/bin/bash

###############################################################################
# ИСПРАВЛЕНИЕ ЗАВИСИМОСТЕЙ В ВИРТУАЛЬНОМ ОКРУЖЕНИИ
# Переустанавливает все зависимости в venv
###############################################################################

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
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

log "🔧 Исправление зависимостей в виртуальном окружении..."

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor || error "Директория не найдена"

# Останавливаем сервис
log "Остановка сервиса..."
systemctl stop reverse-proxy-monitor

# Проверяем и пересоздаем виртуальное окружение если нужно
if [[ ! -f "venv/bin/python" ]]; then
    log "Создание виртуального окружения..."
    python3.11 -m venv venv
fi

# Активируем виртуальное окружение и устанавливаем зависимости
log "Установка зависимостей в venv..."
source venv/bin/activate

# Обновляем pip
pip install --upgrade pip setuptools wheel

# Устанавливаем все зависимости
pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary pydantic pydantic-settings typer passlib[bcrypt] python-jose[cryptography] python-multipart httpx paramiko dnspython cryptography apscheduler jinja2 aiofiles

log "✅ Зависимости установлены"

# Тестируем импорты в виртуальном окружении
log "Тестирование импортов..."
python -c "
try:
    from pydantic_settings import BaseSettings
    print('✅ pydantic_settings')
except ImportError as e:
    print(f'❌ pydantic_settings: {e}')

try:
    import sqlalchemy
    print('✅ sqlalchemy')
except ImportError as e:
    print(f'❌ sqlalchemy: {e}')

try:
    import fastapi
    print('✅ fastapi')
except ImportError as e:
    print(f'❌ fastapi: {e}')

try:
    from backend.config import settings
    print('✅ backend.config')
except ImportError as e:
    print(f'❌ backend.config: {e}')

try:
    from backend.database import engine
    print('✅ backend.database')
except ImportError as e:
    print(f'❌ backend.database: {e}')
"

# Проверяем права доступа
log "Исправление прав доступа..."
chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/
chmod +x /opt/reverse-proxy-monitor/venv/bin/python

# Запускаем сервис обратно
log "Запуск сервиса..."
systemctl start reverse-proxy-monitor

# Проверяем статус
sleep 3
if systemctl is-active --quiet reverse-proxy-monitor; then
    log "✅ Сервис успешно запущен!"
    
    # Показываем последние логи
    echo
    log "Последние логи сервиса:"
    journalctl -u reverse-proxy-monitor -n 10 --no-pager
    
    echo
    log "🎉 Зависимости исправлены!"
    log "Приложение должно работать корректно"
else
    error "❌ Сервис не запустился. Проверьте логи: sudo journalctl -u reverse-proxy-monitor -f"
fi