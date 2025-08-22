#!/usr/bin/env python3
"""
Скрипт для включения/настройки Basic Authentication.
"""
import os
import sys

def update_env_file(basic_auth_enabled=True, username="admin", password="secret"):
    """Обновить .env файл с настройками Basic Auth."""
    env_path = ".env"
    
    # Читаем существующий .env файл
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_lines = f.readlines()
    
    # Удаляем существующие настройки Basic Auth
    env_lines = [line for line in env_lines if not any(
        line.strip().startswith(key) for key in 
        ['BASIC_AUTH_ENABLED', 'BASIC_AUTH_USERNAME', 'BASIC_AUTH_PASSWORD']
    )]
    
    # Добавляем новые настройки
    env_lines.append(f"\n# Basic Authentication Settings\n")
    env_lines.append(f"BASIC_AUTH_ENABLED={'true' if basic_auth_enabled else 'false'}\n")
    env_lines.append(f"BASIC_AUTH_USERNAME={username}\n")
    env_lines.append(f"BASIC_AUTH_PASSWORD={password}\n")
    
    # Записываем обновленный файл
    with open(env_path, 'w') as f:
        f.writelines(env_lines)
    
    print(f"✅ Настройки Basic Auth обновлены в {env_path}")

def main():
    if len(sys.argv) < 2:
        print("🔐 Управление Basic Authentication")
        print("Использование:")
        print("  python3 enable_basic_auth.py enable [username] [password]")
        print("  python3 enable_basic_auth.py disable")
        print()
        print("Примеры:")
        print("  python3 enable_basic_auth.py enable admin secret123")
        print("  python3 enable_basic_auth.py enable")  # использует admin/secret по умолчанию
        print("  python3 enable_basic_auth.py disable")
        return
    
    command = sys.argv[1].lower()
    
    if command == "enable":
        username = sys.argv[2] if len(sys.argv) > 2 else "admin"
        password = sys.argv[3] if len(sys.argv) > 3 else "secret"
        
        update_env_file(basic_auth_enabled=True, username=username, password=password)
        
        print()
        print("🔐 Basic Authentication включена!")
        print(f"   Пользователь: {username}")
        print(f"   Пароль: {password}")
        print()
        print("ℹ️  Перезапустите сервер для применения изменений")
        print("   После перезапуска все страницы будут требовать аутентификацию")
        
    elif command == "disable":
        update_env_file(basic_auth_enabled=False)
        
        print()
        print("✅ Basic Authentication отключена")
        print("ℹ️  Перезапустите сервер для применения изменений")
        
    else:
        print("❌ Неизвестная команда. Используйте 'enable' или 'disable'")

if __name__ == "__main__":
    main()