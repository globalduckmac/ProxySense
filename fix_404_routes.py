#!/usr/bin/env python3
"""
Скрипт диагностики и исправления проблемы 404 Not Found на сервере
Проверяет и исправляет регистрацию маршрутов в main.py
"""

import os
import sys

def check_main_py():
    """Проверяет и исправляет main.py"""
    
    main_file = '/opt/reverse-proxy-monitor/main.py'
    
    if not os.path.exists(main_file):
        print("❌ main.py не найден!")
        return False
    
    with open(main_file, 'r') as f:
        content = f.read()
    
    print(f"📄 Содержимое main.py:")
    print("=" * 50)
    print(content)
    print("=" * 50)
    
    # Проверим что все необходимые импорты есть
    required_imports = [
        'from backend.app import app',
        'from backend.api import auth',
        'from backend.ui import routes'
    ]
    
    missing_imports = []
    for imp in required_imports:
        if imp not in content:
            missing_imports.append(imp)
    
    if missing_imports:
        print(f"⚠️ Отсутствуют импорты: {missing_imports}")
        return False
    
    # Проверим регистрацию роутеров
    required_routers = [
        'app.include_router(auth.router, prefix="/api/auth")',
        'app.include_router(routes.router)'
    ]
    
    missing_routers = []
    for router in required_routers:
        if router not in content:
            missing_routers.append(router)
    
    if missing_routers:
        print(f"⚠️ Не зарегистрированы роутеры: {missing_routers}")
        return False
    
    print("✅ main.py выглядит корректно")
    return True

def fix_main_py():
    """Создает правильный main.py"""
    
    main_file = '/opt/reverse-proxy-monitor/main.py'
    
    correct_main_content = '''"""
Main application entry point for Reverse Proxy & Monitor.
"""
import uvicorn
from backend.app import app
from backend.api import auth
from backend.ui import routes

# Include API routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Include UI routes
app.include_router(routes.router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        log_level="info"
    )
'''
    
    with open(main_file, 'w') as f:
        f.write(correct_main_content)
    
    print("✅ main.py исправлен")

def check_app_py():
    """Проверяет backend/app.py"""
    
    app_file = '/opt/reverse-proxy-monitor/backend/app.py'
    
    if not os.path.exists(app_file):
        print("❌ backend/app.py не найден!")
        return False
    
    with open(app_file, 'r') as f:
        content = f.read()
    
    # Проверим что FastAPI app создан правильно
    if 'app = FastAPI(' not in content:
        print("⚠️ FastAPI app не создан в backend/app.py")
        return False
    
    print("✅ backend/app.py выглядит корректно")
    return True

def check_routes_py():
    """Проверяет backend/ui/routes.py"""
    
    routes_file = '/opt/reverse-proxy-monitor/backend/ui/routes.py'
    
    if not os.path.exists(routes_file):
        print("❌ backend/ui/routes.py не найден!")
        return False
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Проверим что router создан
    if 'router = APIRouter()' not in content:
        print("⚠️ APIRouter не создан в routes.py")
        return False
    
    # Проверим что есть основные маршруты
    if '@router.get("/")' not in content:
        print("⚠️ Главный маршрут / отсутствует")
        return False
    
    print("✅ backend/ui/routes.py выглядит корректно")
    return True

def check_service_status():
    """Проверяет статус сервиса"""
    
    print("\n🔍 Проверка статуса сервиса:")
    os.system("systemctl status reverse-proxy-monitor --no-pager -l")

def restart_service():
    """Перезапускает сервис"""
    print("\n🔄 Перезапуск сервиса...")
    os.system("systemctl restart reverse-proxy-monitor")
    print("✅ Сервис перезапущен")
    
    print("\n📋 Проверка статуса после перезапуска:")
    os.system("systemctl status reverse-proxy-monitor --no-pager -l")

def check_logs():
    """Показывает последние логи"""
    print("\n📜 Последние 20 строк логов:")
    os.system("journalctl -u reverse-proxy-monitor --no-pager -n 20")

if __name__ == "__main__":
    print("🔧 Диагностика проблемы 404 Not Found...")
    
    # Проверяем все файлы
    main_ok = check_main_py()
    app_ok = check_app_py()
    routes_ok = check_routes_py()
    
    if not main_ok:
        print("\n🔧 Исправляем main.py...")
        fix_main_py()
        main_ok = True
    
    if main_ok and app_ok and routes_ok:
        print("\n✅ Все файлы выглядят корректно")
        restart_service()
        check_logs()
    else:
        print("\n❌ Найдены проблемы в файлах приложения")
        print("Необходимо проверить:")
        if not app_ok:
            print("- backend/app.py")
        if not routes_ok:
            print("- backend/ui/routes.py")
    
    # Всегда показываем статус в конце
    check_service_status()