#!/usr/bin/env python3
"""Простой скрипт создания админа - запускать из /opt/reverse-proxy-monitor"""
import sys
import os
sys.path.insert(0, '/opt/reverse-proxy-monitor')

from backend.database import SessionLocal
from backend.models import User  
from backend.auth import get_password_hash

db = SessionLocal()

try:
    # Проверяем есть ли admin
    admin = db.query(User).filter(User.username == 'admin').first()
    if admin:
        print('✅ Админ admin уже существует')
        print(f'   Роль: {admin.role}')
    else:
        # Создаем нового админа
        new_admin = User(
            username='admin',
            email='admin@example.com', 
            password_hash=get_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        db.add(new_admin)
        db.commit()
        print('✅ Админ создан: admin/admin123')
        
except Exception as e:
    print(f'❌ Ошибка: {e}')
    db.rollback()
finally:
    db.close()