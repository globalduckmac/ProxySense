#!/usr/bin/env python3
"""
Демонстрация Basic Authentication функционала.
"""
import os
import time
import subprocess
import sys
import threading

def log(message):
    print(f"[DEMO] {message}")

def run_command(cmd):
    """Выполнить команду."""
    log(f"Выполняю: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    return result.returncode == 0

def demo_basic_auth():
    """Демонстрация Basic Auth функционала."""
    
    log("🔐 ДЕМОНСТРАЦИЯ BASIC AUTHENTICATION")
    log("=" * 50)
    
    # Показываем текущее состояние
    log("📋 Текущие настройки в backend/config.py:")
    try:
        with open('backend/config.py', 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if 'BASIC_AUTH' in line:
                    print(f"   {i+1:3}: {line.strip()}")
    except Exception as e:
        log(f"Ошибка чтения конфига: {e}")
    
    print()
    
    # Демонстрируем включение Basic Auth
    log("🔧 Включаем Basic Authentication...")
    if run_command("python3 enable_basic_auth.py enable demo password123"):
        log("✅ Basic Auth включена")
    else:
        log("❌ Ошибка включения Basic Auth")
        return
    
    # Показываем обновленный .env файл
    log("📄 Содержимое .env файла:")
    try:
        with open('.env', 'r') as f:
            content = f.read()
            print(content)
    except FileNotFoundError:
        log("⚠️  Файл .env не найден")
    
    print()
    
    log("ℹ️  Для применения изменений нужно перезапустить сервер")
    log("   В Replit сервер перезапустится автоматически при изменении файлов")
    
    # Ждем чтобы пользователь видел изменения
    log("⏱️  Ждем 5 секунд для перезапуска...")
    time.sleep(5)
    
    log("🧪 Теперь можно протестировать Basic Auth:")
    log("   1. Откройте браузер и перейдите на главную страницу")
    log("   2. Должно появиться окно для ввода логина/пароля")
    log("   3. Введите: demo / password123")
    log("   4. После успешной аутентификации откроется интерфейс")
    
    print()
    
    # Показываем как отключить
    log("📋 Чтобы отключить Basic Auth, выполните:")
    log("   python3 enable_basic_auth.py disable")
    
    print()
    
    log("🔧 MIDDLEWARE КОМПОНЕНТЫ:")
    log("   ✅ BasicAuthMiddleware - проверка HTTP Basic заголовков")
    log("   ✅ Исключение статических файлов (/static/*)")
    log("   ✅ Защита от timing атак с secrets.compare_digest()")
    log("   ✅ Настраиваемые учетные данные через .env")
    
    print()
    
    log("🎯 ПРЕИМУЩЕСТВА BASIC AUTH:")
    log("   • Дополнительный слой защиты перед JWT аутентификацией")
    log("   • Защищает от случайного доступа и ботов")
    log("   • Простота настройки и управления")
    log("   • Стандартный HTTP механизм")
    log("   • Работает со всеми браузерами")

def main():
    if not os.path.exists('backend/config.py'):
        log("❌ Не найден файл backend/config.py")
        log("   Запускайте скрипт из корневой директории проекта")
        return
    
    demo_basic_auth()

if __name__ == "__main__":
    main()