#!/usr/bin/env python3
"""
Диагностика проблем с сервисом reverse-proxy-monitor
Запускать из /opt/reverse-proxy-monitor
"""
import sys
import os
import subprocess
import traceback

def log(message):
    print(f"[DEBUG] {message}")

def run_command(cmd, capture_output=True):
    """Выполнить команду и вернуть результат"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def check_service_status():
    """Проверить статус сервиса"""
    log("Проверка статуса сервиса...")
    
    retcode, stdout, stderr = run_command("systemctl status reverse-proxy-monitor")
    print("=== СТАТУС СЕРВИСА ===")
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    print()

def check_service_logs():
    """Проверить логи сервиса"""
    log("Проверка логов сервиса...")
    
    retcode, stdout, stderr = run_command("journalctl -u reverse-proxy-monitor --no-pager -n 20")
    print("=== ЛОГИ СЕРВИСА ===")
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    print()

def check_environment():
    """Проверить окружение"""
    log("Проверка окружения...")
    
    print("=== ОКРУЖЕНИЕ ===")
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Python путь: {sys.executable}")
    print(f"Python версия: {sys.version}")
    
    # Проверяем файлы
    files_to_check = [
        'main.py', 
        'backend/app.py', 
        'backend/models.py',
        'backend/config.py',
        'venv/bin/python',
        '.env'
    ]
    
    for file in files_to_check:
        exists = "✅" if os.path.exists(file) else "❌"
        print(f"{exists} {file}")
    print()

def test_import():
    """Тестировать импорты"""
    log("Тестирование импортов...")
    
    print("=== ТЕСТ ИМПОРТОВ ===")
    
    # Добавляем текущую директорию в путь
    sys.path.insert(0, '/opt/reverse-proxy-monitor')
    
    modules_to_test = [
        'backend.config',
        'backend.database', 
        'backend.models',
        'backend.app',
        'backend.api.auth',
        'backend.ui.routes'
    ]
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module}: {e}")
            traceback.print_exc()
    print()

def test_database():
    """Тестировать подключение к БД"""
    log("Тестирование подключения к базе данных...")
    
    print("=== ТЕСТ БАЗЫ ДАННЫХ ===")
    sys.path.insert(0, '/opt/reverse-proxy-monitor')
    
    try:
        from backend.database import engine, SessionLocal
        from backend.models import User
        
        # Тестируем подключение
        with engine.connect() as conn:
            print("✅ Подключение к БД успешно")
        
        # Тестируем сессию
        db = SessionLocal()
        users = db.query(User).count()
        print(f"✅ Количество пользователей: {users}")
        db.close()
        
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        traceback.print_exc()
    print()

def test_run_main():
    """Попробовать запустить main.py напрямую"""
    log("Попытка запуска main.py...")
    
    print("=== ТЕСТ ЗАПУСКА MAIN.PY ===")
    
    # Проверяем виртуальное окружение
    venv_python = "/opt/reverse-proxy-monitor/venv/bin/python"
    if os.path.exists(venv_python):
        print(f"✅ venv Python найден: {venv_python}")
        
        # Пробуем запустить с таймаутом
        try:
            cmd = f"cd /opt/reverse-proxy-monitor && timeout 10s {venv_python} main.py"
            retcode, stdout, stderr = run_command(cmd)
            
            print(f"Return code: {retcode}")
            if stdout:
                print("STDOUT:")
                print(stdout)
            if stderr:
                print("STDERR:")
                print(stderr)
                
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
    else:
        print(f"❌ venv Python не найден: {venv_python}")
    print()

def main():
    print("🔍 ДИАГНОСТИКА REVERSE-PROXY-MONITOR")
    print("=" * 50)
    
    # Переходим в рабочую директорию
    try:
        os.chdir('/opt/reverse-proxy-monitor')
    except Exception as e:
        print(f"❌ Не удалось перейти в /opt/reverse-proxy-monitor: {e}")
        return
    
    check_environment()
    check_service_status()
    check_service_logs()
    test_import()
    test_database()
    test_run_main()
    
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("1. Проверьте логи сервиса выше на наличие ошибок")
    print("2. Убедитесь что все модули импортируются корректно")
    print("3. Проверьте настройки базы данных")
    print("4. При необходимости перезапустите сервис: systemctl restart reverse-proxy-monitor")

if __name__ == "__main__":
    main()