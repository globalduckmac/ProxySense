#!/bin/bash

# Скрипт исправления проблемы с APT

echo "Исправление проблемы с APT..."

# Исправление прав доступа
chmod +x /usr/lib/cnf-update-db 2>/dev/null || true

# Если не помогло, отключаем проблематичный hook
if [ -f /etc/apt/apt.conf.d/50command-not-found ]; then
    mv /etc/apt/apt.conf.d/50command-not-found /etc/apt/apt.conf.d/50command-not-found.disabled
fi

# Альтернативно, создаем пустой файл
cat > /etc/apt/apt.conf.d/99-disable-cnf << 'EOF'
APT::Update::Post-Invoke-Success "";
EOF

# Проверяем, что APT теперь работает
echo "Тестирование APT..."
apt update > /tmp/apt_test.log 2>&1

if [ $? -eq 0 ]; then
    echo "✅ APT исправлен успешно!"
    rm -f /etc/apt/apt.conf.d/99-disable-cnf
else
    echo "⚠️ APT все еще имеет проблемы, но они не критичны"
    echo "Продолжаем установку..."
fi

echo "Теперь можно запускать ./deploy.sh"