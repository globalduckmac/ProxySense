#!/bin/bash

###############################################################################
# СКРИПТ ИСПРАВЛЕНИЯ СУЩЕСТВУЮЩЕЙ УСТАНОВКИ
# Исправляет проблемы в уже установленном приложении
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
    exit 1
}

if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
fi

log "🔧 Исправление существующей установки..."

# Останавливаем сервис
log "Останавливаем сервис..."
systemctl stop reverse-proxy-monitor || true

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor

# Сохраняем текущий .env если есть
if [[ -f ".env" ]]; then
    log "Создаем резервную копию .env..."
    cp .env .env.backup
fi

# Очищаем и обновляем код
log "Обновление кода приложения..."
if [[ -d ".git" ]]; then
    git stash push -m "Auto-stash before fix $(date)" || true
    git pull origin main || {
        warn "Ошибка git pull, пересоздаем репозиторий..."
        cd /opt
        rm -rf reverse-proxy-monitor
        mkdir -p reverse-proxy-monitor
        cd reverse-proxy-monitor
        git clone https://github.com/globalduckmac/ProxySense.git .
        
        # Восстанавливаем .env если был
        if [[ -f "/opt/reverse-proxy-monitor.env.backup" ]]; then
            cp /opt/reverse-proxy-monitor.env.backup .env
        fi
    }
else
    # Если нет .git, очищаем и клонируем заново
    log "Очистка и клонирование репозитория..."
    rm -rf /opt/reverse-proxy-monitor/*
    rm -rf /opt/reverse-proxy-monitor/.[^.]*
    git clone https://github.com/globalduckmac/ProxySense.git .
fi

# Восстанавливаем .env если был сохранен
if [[ -f ".env.backup" ]]; then
    log "Восстанавливаем .env файл..."
    mv .env.backup .env
fi

# Обновляем виртуальное окружение
log "Обновление зависимостей..."
source venv/bin/activate || {
    log "Создаем новое виртуальное окружение..."
    python3.11 -m venv venv
    source venv/bin/activate
}

pip install --upgrade pip
pip install -r setup_requirements.txt

# Исправляем main.py (критическое исправление 404)
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

# Исправляем настройки cookie в auth.py
log "Исправление настроек аутентификации..."
if [[ -f "backend/auth.py" ]]; then
    sed -i 's/secure=True/secure=False/g' backend/auth.py
    sed -i 's/samesite="strict"/samesite="lax"/g' backend/auth.py
    sed -i 's/samesite="Strict"/samesite="lax"/g' backend/auth.py
    log "Cookie настройки исправлены для reverse proxy"
fi

# Исправляем настройки пула БД
log "Исправление настроек пула БД..."
find backend/ -name "*.py" -exec sed -i 's/pool_size=5/pool_size=20/g' {} \;
find backend/ -name "*.py" -exec sed -i 's/max_overflow=10/max_overflow=30/g' {} \;
log "Пул БД увеличен до 20 соединений"

# Проверяем .env файл
log "Проверка .env файла..."
if [[ -f ".env" ]]; then
    # Удаляем проблемные переменные если есть
    sed -i '/^HOST=/d' .env
    sed -i '/^PORT=/d' .env
    
    # Добавляем исправления если их нет
    if ! grep -q "COOKIE_SECURE" .env; then
        echo "" >> .env
        echo "# Cookie Settings (исправление для reverse proxy)" >> .env
        echo "COOKIE_SECURE=false" >> .env
        echo "COOKIE_SAMESITE=lax" >> .env
    fi
    
    if ! grep -q "DB_POOL_SIZE" .env; then
        echo "" >> .env
        echo "# Database Pool Settings" >> .env
        echo "DB_POOL_SIZE=20" >> .env
        echo "DB_MAX_OVERFLOW=30" >> .env
        echo "DB_POOL_TIMEOUT=60" >> .env
    fi
    
    log ".env файл проверен и исправлен"
else
    warn ".env файл не найден - создайте его вручную"
fi

# Проверяем есть ли admin пользователь
log "Проверка администратора..."
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
    print(f'Информация об админе: {e}')
"

# Устанавливаем правильные права
log "Исправление прав доступа..."
chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/
chmod 600 .env
chmod +x main.py

# Запускаем сервис
log "Запуск сервиса..."
systemctl start reverse-proxy-monitor

# Ждем и проверяем
sleep 5

log "Проверка статуса..."
if systemctl is-active --quiet reverse-proxy-monitor; then
    echo -e "${GREEN}✅ Сервис запущен успешно${NC}"
else
    echo -e "${RED}❌ Сервис не запустился${NC}"
    systemctl status reverse-proxy-monitor --no-pager -l
fi

# Тест HTTP
log "Тест HTTP соединения..."
if curl -s http://localhost:5000/ > /dev/null; then
    echo -e "${GREEN}✅ HTTP: работает${NC}"
else
    echo -e "${RED}❌ HTTP: не отвечает${NC}"
fi

# Показываем последние логи
log "Последние логи сервиса..."
journalctl -u reverse-proxy-monitor --no-pager -n 10

echo -e "\n${GREEN}╔══════════════════════════════════════════════╗"
echo -e "║              ИСПРАВЛЕНИЯ ПРИМЕНЕНЫ           ║"
echo -e "║                                              ║"  
echo -e "║  🌐 URL: http://$(hostname -I | awk '{print $1}')/"
echo -e "║  👤 Логин: admin                             ║"
echo -e "║  🔑 Пароль: admin123                         ║"
echo -e "╚══════════════════════════════════════════════╝${NC}"

log "🎉 ИСПРАВЛЕНИЯ ЗАВЕРШЕНЫ!"