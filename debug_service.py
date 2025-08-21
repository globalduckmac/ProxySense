#!/usr/bin/env python3
"""
Отладка проблем запуска сервиса
"""

import os
import subprocess
import time

def check_service_status():
    """Проверяет статус сервиса"""
    print("🔍 Статус сервиса:")
    os.system("systemctl status reverse-proxy-monitor --no-pager")
    
def check_service_logs():
    """Показывает последние логи сервиса"""
    print("\n📜 Последние 30 строк логов:")
    os.system("journalctl -u reverse-proxy-monitor --no-pager -n 30")

def test_manual_start():
    """Тестирует ручной запуск приложения"""
    print("\n🧪 Тестирование ручного запуска:")
    print("Попытка запуска приложения вручную...")
    
    os.chdir("/opt/reverse-proxy-monitor")
    
    # Активируем виртуальное окружение и запускаем
    result = subprocess.run([
        "/bin/bash", "-c", 
        "cd /opt/reverse-proxy-monitor && source venv/bin/activate && python main.py &"
    ], capture_output=True, text=True, timeout=10)
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    
    # Дадим время на запуск
    time.sleep(3)
    
    # Проверим порт
    port_result = subprocess.run(["netstat", "-tlnp", "|", "grep", "5000"], 
                                shell=True, capture_output=True, text=True)
    print("\nПорт 5000:", port_result.stdout)

def check_dependencies():
    """Проверяет зависимости"""
    print("\n📦 Проверка зависимостей:")
    
    os.chdir("/opt/reverse-proxy-monitor")
    
    # Проверяем установку пакетов
    result = subprocess.run([
        "/bin/bash", "-c",
        "cd /opt/reverse-proxy-monitor && source venv/bin/activate && pip list | grep -E '(fastapi|uvicorn|sqlalchemy)'"
    ], capture_output=True, text=True)
    
    print("Установленные пакеты:")
    print(result.stdout)
    
    if result.stderr:
        print("Ошибки:", result.stderr)

def check_python_syntax():
    """Проверяет синтаксис Python файлов"""
    print("\n🐍 Проверка синтаксиса:")
    
    files_to_check = [
        "/opt/reverse-proxy-monitor/main.py",
        "/opt/reverse-proxy-monitor/backend/app.py",
        "/opt/reverse-proxy-monitor/backend/ui/routes.py"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            result = subprocess.run([
                "python3", "-m", "py_compile", file_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ {file_path} - синтаксис OK")
            else:
                print(f"❌ {file_path} - ошибка синтаксиса:")
                print(result.stderr)

def check_permissions():
    """Проверяет права доступа"""
    print("\n🔐 Проверка прав доступа:")
    os.system("ls -la /opt/reverse-proxy-monitor/ | head -10")
    
    print("\nПользователь rpmonitor:")
    os.system("id rpmonitor")

def fix_service_issues():
    """Пытается исправить проблемы сервиса"""
    print("\n🔧 Исправление проблем:")
    
    # Останавливаем сервис
    print("Останавливаем сервис...")
    os.system("systemctl stop reverse-proxy-monitor")
    
    # Проверяем что процессы убиты
    print("Убиваем все процессы Python...")
    os.system("pkill -f 'python.*main.py' || true")
    
    # Меняем владельца файлов
    print("Исправляем права доступа...")
    os.system("chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/")
    
    # Перезагружаем systemd
    print("Перезагружаем systemd...")
    os.system("systemctl daemon-reload")
    
    # Запускаем сервис
    print("Запускаем сервис...")
    os.system("systemctl start reverse-proxy-monitor")
    
    # Даем время на запуск
    time.sleep(5)
    
    print("Проверяем статус...")
    os.system("systemctl status reverse-proxy-monitor --no-pager")

if __name__ == "__main__":
    print("🔧 Отладка проблем сервиса reverse-proxy-monitor...")
    
    check_service_status()
    check_service_logs()
    check_python_syntax()
    check_dependencies()
    check_permissions()
    
    print("\n" + "="*50)
    print("ПОПЫТКА ИСПРАВЛЕНИЯ")
    print("="*50)
    
    fix_service_issues()
    
    print("\n🌐 Финальное тестирование:")
    time.sleep(2)
    os.system("curl -I http://localhost:5000/ || echo 'Соединение не удалось'")