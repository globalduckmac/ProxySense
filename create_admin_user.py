#!/usr/bin/env python3
"""
Создание администратора для Reverse Proxy Monitor
Использовать: python3 create_admin_user.py
"""
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, '/opt/reverse-proxy-monitor')
os.chdir('/opt/reverse-proxy-monitor')

try:
    from backend.database import SessionLocal, engine
    from backend.models import User
    from backend.auth import get_password_hash
    from sqlalchemy.orm import Session
    
    def create_admin():
        """Создать администратора"""
        db = SessionLocal()
        
        try:
            # Проверяем есть ли уже admin
            existing_admin = db.query(User).filter(User.username == "admin").first()
            
            if existing_admin:
                print("✅ Администратор admin уже существует")
                print(f"   ID: {existing_admin.id}")
                print(f"   Email: {existing_admin.email}")
                print(f"   Активен: {existing_admin.is_active}")
                print(f"   Админ: {existing_admin.is_admin}")
                return True
            
            # Создаем админа
            admin_user = User(
                username="admin",
                email="admin@example.com", 
                password_hash=get_password_hash("admin123"),
                is_admin=True,
                is_active=True
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            print("✅ Администратор создан успешно!")
            print("   Логин: admin")
            print("   Пароль: admin123")
            print(f"   ID: {admin_user.id}")
            print("   ОБЯЗАТЕЛЬНО смените пароль после первого входа!")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка создания администратора: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    if __name__ == "__main__":
        print("🔧 Создание администратора...")
        print(f"📁 Рабочая директория: {os.getcwd()}")
        
        if create_admin():
            print("\n🎉 Готово! Можете войти в систему:")
            print("   http://ваш-сервер:5000/")
        else:
            print("\n❌ Не удалось создать администратора")
            sys.exit(1)
            
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("\n🔧 Возможные решения:")
    print("1. Активируйте виртуальное окружение:")
    print("   cd /opt/reverse-proxy-monitor")
    print("   source venv/bin/activate")
    print("   python3 create_admin_user.py")
    print("\n2. Или выполните с полным путем:")
    print("   cd /opt/reverse-proxy-monitor")
    print("   ./venv/bin/python create_admin_user.py")
    sys.exit(1)
except Exception as e:
    print(f"❌ Общая ошибка: {e}")
    sys.exit(1)