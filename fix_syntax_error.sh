#!/bin/bash
# Быстрое исправление синтаксической ошибки в ui/routes.py

cd /opt/reverse-proxy-monitor

echo "🔧 Исправление синтаксической ошибки..."

# Создаем backup
cp backend/ui/routes.py backend/ui/routes.py.backup.syntax.$(date +%Y%m%d_%H%M%S)

# Исправляем синтаксическую ошибку
python3 << 'EOF'
import re

with open('backend/ui/routes.py', 'r') as f:
    content = f.read()

# Исправляем проблемную строку
# Ищем блок set_cookie и заменяем целиком
pattern = r'response\.set_cookie\(\s*key="access_token",\s*value=access_token,\s*max_age=settings\.ACCESS_TOKEN_EXPIRE_MINUTES \* 60,\s*httponly=True,\s*secure=False,.*?samesite="lax".*?\)'

replacement = '''response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )'''

content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

with open('backend/ui/routes.py', 'w') as f:
    f.write(content)

print("✅ Синтаксическая ошибка исправлена")
EOF

# Проверяем синтаксис
echo "🔍 Проверка синтаксиса Python..."
python3 -m py_compile backend/ui/routes.py

if [ $? -eq 0 ]; then
    echo "✅ Синтаксис корректен"
    
    # Перезапускаем сервис
    echo "🔄 Перезапуск сервиса..."
    systemctl restart reverse-proxy-monitor
    
    sleep 5
    if systemctl is-active --quiet reverse-proxy-monitor; then
        echo "✅ Сервис успешно запущен"
        echo "🌐 Теперь можете войти: http://$(hostname -I | awk '{print $1}'):5000/"
        echo "   Логин: admin"
        echo "   Пароль: admin123"
    else
        echo "❌ Сервис не запустился, проверьте логи"
        journalctl -u reverse-proxy-monitor --no-pager -n 10
    fi
else
    echo "❌ Синтаксическая ошибка все еще присутствует"
fi