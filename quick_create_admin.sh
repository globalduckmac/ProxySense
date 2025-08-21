#!/bin/bash

###############################################################################
# БЫСТРОЕ СОЗДАНИЕ АДМИНИСТРАТОРА
# Создает пользователя admin с паролем admin123
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

if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
fi

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor

# Проверяем существование виртуального окружения
if [[ ! -d "venv" ]]; then
    error "Виртуальное окружение не найдено. Запустите сначала deploy скрипт."
fi

log "Создание администратора..."

# Активируем виртуальное окружение и создаем админа
source venv/bin/activate

python3 -c "
import sys
sys.path.insert(0, '/opt/reverse-proxy-monitor')

try:
    from backend.database import SessionLocal
    from backend.models import User
    from backend.auth import get_password_hash
    
    db = SessionLocal()
    
    # Проверяем есть ли уже admin
    existing_admin = db.query(User).filter(User.username == 'admin').first()
    
    if existing_admin:
        print('✅ Администратор admin уже существует')
        print(f'   ID: {existing_admin.id}')
        print(f'   Email: {existing_admin.email}')
        print(f'   Активен: {existing_admin.is_active}')
        print(f'   Админ: {existing_admin.is_admin}')
    else:
        # Создаем админа
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=get_password_hash('admin123'),
            is_admin=True,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print('✅ Администратор создан успешно!')
        print('   Логин: admin')
        print('   Пароль: admin123')
        print(f'   ID: {admin_user.id}')
        print('   ОБЯЗАТЕЛЬНО смените пароль после первого входа!')
    
    db.close()
    
except Exception as e:
    print(f'❌ Ошибка: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"

# Проверяем статус сервиса
log "Проверка статуса сервиса..."
if systemctl is-active --quiet reverse-proxy-monitor; then
    echo -e "${GREEN}✅ Сервис работает${NC}"
else
    echo -e "${YELLOW}⚠️ Сервис не запущен, пытаемся запустить...${NC}"
    systemctl start reverse-proxy-monitor
    sleep 3
    if systemctl is-active --quiet reverse-proxy-monitor; then
        echo -e "${GREEN}✅ Сервис запущен${NC}"
    else
        echo -e "${RED}❌ Не удалось запустить сервис${NC}"
    fi
fi

# Получаем IP адрес сервера
SERVER_IP=$(hostname -I | awk '{print $1}')

echo -e "\n${GREEN}╔══════════════════════════════════════════════╗"
echo -e "║              АДМИНИСТРАТОР СОЗДАН             ║"
echo -e "║                                              ║"
echo -e "║  🌐 URL: http://$SERVER_IP:5000/"
echo -e "║  👤 Логин: admin                             ║"
echo -e "║  🔑 Пароль: admin123                         ║"
echo -e "║                                              ║"
echo -e "║  ⚠️  ОБЯЗАТЕЛЬНО смените пароль после входа!  ║"
echo -e "╚══════════════════════════════════════════════╝${NC}"

log "🎉 Готово!"