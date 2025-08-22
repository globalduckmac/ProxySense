#!/bin/bash

###############################################################################
# ИСПРАВЛЕНИЕ ОШИБКИ PROBE GLANCES
# Исправляет ошибку "cannot unpack non-iterable bool object"
###############################################################################

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
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

log "🔧 Исправление ошибки probe Glances..."

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor || error "Директория не найдена"

# Останавливаем сервис
log "Остановка сервиса..."
systemctl stop reverse-proxy-monitor

# Создаем бэкап
log "Создание бэкапа..."
cp backend/api/servers.py backend/api/servers.py.backup.$(date +%s)

# Исправляем ошибку распаковки в probe-glances
log "Исправление ошибки распаковки..."
sed -i '/success, message = await glances_client.test_connection/c\        success = await glances_client.test_connection(glances_url, auth, headers)' backend/api/servers.py

sed -i '/return {"success": True, "message": message}/c\            return {"success": True, "message": "Glances API connection successful"}' backend/api/servers.py

sed -i '/return {"success": False, "message": message}/c\            return {"success": False, "message": "Failed to connect to Glances API"}' backend/api/servers.py

# Проверяем права доступа
log "Исправление прав доступа..."
chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/

# Запускаем сервис
log "Запуск сервиса..."
systemctl start reverse-proxy-monitor

# Ждем запуска
sleep 5

# Проверяем статус
if systemctl is-active --quiet reverse-proxy-monitor; then
    log "✅ Сервис успешно запущен с исправленным probe Glances"
    
    echo
    log "🧪 Теперь тест Glances должен работать без ошибок!"
    log "Попробуйте нажать 'Тест Glances' в панели серверов"
    
else
    error "❌ Сервис не запустился. Проверьте логи: sudo journalctl -u reverse-proxy-monitor -f"
fi

log "🎉 Исправление завершено!"