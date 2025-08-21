#!/bin/bash
# Исправление настроек куков для аутентификации через Nginx reverse proxy

set -e

cd /opt/reverse-proxy-monitor

echo "🔧 Исправление настроек куков для аутентификации..."

# Создаем backup
cp backend/ui/routes.py backend/ui/routes.py.backup.$(date +%Y%m%d_%H%M%S)

# Исправляем настройки куков простым sed
sed -i 's/secure=not settings\.DEBUG/secure=False/g' backend/ui/routes.py

# Добавляем samesite="lax" после httponly=True
sed -i '/httponly=True,$/a\        samesite="lax"  # Исправлено для работы с Nginx reverse proxy' backend/ui/routes.py

echo "✅ Настройки куков исправлены"

# Перезапуск сервиса
echo "🔄 Перезапуск сервиса..."
systemctl restart reverse-proxy-monitor

# Проверка статуса
sleep 5
if systemctl is-active --quiet reverse-proxy-monitor; then
    echo "✅ Сервис успешно перезапущен"
    echo "🌐 Теперь можете войти в систему: http://$(hostname -I | awk '{print $1}'):5000/"
    echo "   Логин: admin"
    echo "   Пароль: admin123"
else
    echo "❌ Ошибка при перезапуске сервиса"
    journalctl -u reverse-proxy-monitor --no-pager -n 20
fi

rm -f /tmp/fix_cookies.py