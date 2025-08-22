#!/bin/bash

###############################################################################
# ИСПРАВЛЕНИЕ СЕТЕВОГО ДОСТУПА
# Настраивает файрвол и Nginx для доступа к приложению
###############################################################################

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
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
}

# Проверка root
if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
    exit 1
fi

log "🔧 Исправление сетевого доступа..."

# 1. Проверка и настройка файрвола
log "Настройка файрвола UFW..."

if command -v ufw >/dev/null 2>&1; then
    # Включаем UFW если не включен
    ufw --force enable
    
    # Разрешаем SSH (важно!)
    ufw allow ssh
    ufw allow 22/tcp
    
    # Разрешаем HTTP и HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # Разрешаем порт 5000 для прямого доступа
    ufw allow 5000/tcp
    
    log "✅ Файрвол настроен"
    ufw status
else
    warn "UFW не установлен, пропускаем"
fi

# 2. Проверка и перезапуск Nginx
log "Проверка Nginx..."

if systemctl is-active --quiet nginx; then
    log "✅ Nginx запущен"
else
    log "Запуск Nginx..."
    systemctl start nginx
    systemctl enable nginx
fi

# Проверим конфигурацию Nginx
if [[ -f "/etc/nginx/sites-enabled/reverse-proxy-monitor" ]]; then
    log "✅ Конфигурация Nginx найдена"
    
    # Тестируем конфигурацию
    if nginx -t; then
        log "✅ Конфигурация Nginx корректна"
        systemctl reload nginx
    else
        error "❌ Ошибка в конфигурации Nginx"
        # Создаем базовую конфигурацию
        log "Создание базовой конфигурации Nginx..."
        
        cat > /etc/nginx/sites-available/reverse-proxy-monitor << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF
        
        # Включаем конфигурацию
        ln -sf /etc/nginx/sites-available/reverse-proxy-monitor /etc/nginx/sites-enabled/
        
        # Удаляем дефолтный сайт если есть
        rm -f /etc/nginx/sites-enabled/default
        
        # Тестируем и перезапускаем
        if nginx -t; then
            systemctl restart nginx
            log "✅ Nginx перенастроен"
        else
            error "❌ Проблема с Nginx конфигурацией"
        fi
    fi
else
    warn "❌ Конфигурация Nginx не найдена, создаем..."
    
    # Создаем конфигурацию с нуля
    cat > /etc/nginx/sites-available/reverse-proxy-monitor << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF
    
    # Включаем конфигурацию
    ln -sf /etc/nginx/sites-available/reverse-proxy-monitor /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Перезапускаем Nginx
    systemctl restart nginx
    log "✅ Nginx настроен"
fi

# 3. Проверка портов
log "Проверка портов..."
if command -v netstat >/dev/null 2>&1; then
    netstat -tlnp | grep -E ":(80|443|5000) " || warn "Некоторые порты не прослушиваются"
else
    ss -tlnp | grep -E ":(80|443|5000) " || warn "Некоторые порты не прослушиваются"
fi

# 4. Тест локального подключения
log "Тест локального подключения..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/ | grep -E "200|302"; then
    log "✅ Приложение отвечает на порту 5000"
else
    warn "❌ Проблема с подключением к порту 5000"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -E "200|302"; then
    log "✅ Nginx проксирует корректно"
else
    warn "❌ Проблема с Nginx проксированием"
fi

# 5. Определение внешнего IP
EXTERNAL_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "неизвестен")

log "🎉 Настройка завершена!"
echo
echo "=== ДОСТУП К ПРИЛОЖЕНИЮ ==="
echo "🌐 Через Nginx (порт 80): http://${EXTERNAL_IP}"
echo "🔗 Прямой доступ (порт 5000): http://${EXTERNAL_IP}:5000"
echo "🔑 Логин: admin"
echo "🔑 Пароль: admin123"
echo
echo "=== ПРОВЕРЬТЕ ==="
echo "1. Откройте http://${EXTERNAL_IP} в браузере"
echo "2. Если не работает - проверьте у хостера настройки файрвола"
echo "3. Логи Nginx: sudo tail -f /var/log/nginx/error.log"
echo "4. Логи приложения: sudo journalctl -u reverse-proxy-monitor -f"