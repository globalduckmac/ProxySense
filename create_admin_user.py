#!/usr/bin/env python3
"""
Скрипт создания администратора для Reverse Proxy Monitor
Запускать на сервере в директории приложения
"""
import os
import sys
sys.path.insert(0, '/opt/reverse-proxy-monitor')

# Установка переменной окружения для базы данных
if 'DATABASE_URL' not in os.environ:
    # Попробуем прочитать из .env файла
    env_file = '/opt/reverse-proxy-monitor/.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.split('=', 1)[1].strip()
                    os.environ['DATABASE_URL'] = db_url
                    break

try:
    from backend.database import get_db
    from backend.models import User
    from backend.auth import get_password_hash
    
    # Создаем сессию БД
    db = next(get_db())
    
    # Удаляем старого админа если есть
    existing_admin = db.query(User).filter(User.username == 'admin').first()
    if existing_admin:
        db.delete(existing_admin)
        db.commit()
        print('Старый администратор удален')
    
    # Создаем нового админа
    admin_user = User(
        username='admin',
        email='admin@localhost',
        password_hash=get_password_hash('admin123'),
        is_active=True,
        role='admin'
    )
    db.add(admin_user)
    db.commit()
    print('✅ Администратор создан: admin / admin123')
    
    # Проверяем что создался
    check_admin = db.query(User).filter(User.username == 'admin').first()
    if check_admin:
        print(f'✅ Подтверждено: пользователь {check_admin.username} создан с ролью {check_admin.role}')
        print(f'Email: {check_admin.email}')
        print(f'Активен: {check_admin.is_active}')
    else:
        print('❌ Ошибка: администратор не найден')
        
    db.close()
    
except Exception as e:
    print(f'❌ Ошибка создания администратора: {e}')
    import traceback
    traceback.print_exc()