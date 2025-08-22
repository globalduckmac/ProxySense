#!/usr/bin/env python3
"""
Управление Basic Authentication учетными данными.
"""
import os
import sys

def show_current_settings():
    """Показать текущие настройки."""
    print("📋 Текущие настройки Basic Auth:")
    
    # Читаем из .env файла
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            if line.strip().startswith(('BASIC_AUTH_')):
                key, value = line.strip().split('=', 1)
                if 'PASSWORD' in key:
                    value = '*' * len(value)  # Маскируем пароль
                print(f"   {key}: {value}")
    else:
        print("   Файл .env не найден")
    
    print()

def change_credentials(username=None, password=None):
    """Изменить учетные данные."""
    if not username:
        username = input("Введите новое имя пользователя: ").strip()
    if not password:
        password = input("Введите новый пароль: ").strip()
    
    if not username or not password:
        print("❌ Имя пользователя и пароль не могут быть пустыми")
        return False
    
    # Обновляем .env файл
    env_path = ".env"
    env_lines = []
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_lines = f.readlines()
    
    # Удаляем старые настройки
    env_lines = [line for line in env_lines if not any(
        line.strip().startswith(key) for key in 
        ['BASIC_AUTH_USERNAME', 'BASIC_AUTH_PASSWORD']
    )]
    
    # Добавляем новые
    updated = False
    for i, line in enumerate(env_lines):
        if line.strip().startswith('BASIC_AUTH_ENABLED'):
            # Вставляем после BASIC_AUTH_ENABLED
            env_lines.insert(i + 1, f"BASIC_AUTH_USERNAME={username}\n")
            env_lines.insert(i + 2, f"BASIC_AUTH_PASSWORD={password}\n")
            updated = True
            break
    
    if not updated:
        # Добавляем в конец
        env_lines.append(f"BASIC_AUTH_USERNAME={username}\n")
        env_lines.append(f"BASIC_AUTH_PASSWORD={password}\n")
    
    # Записываем файл
    with open(env_path, 'w') as f:
        f.writelines(env_lines)
    
    print(f"✅ Учетные данные обновлены:")
    print(f"   Пользователь: {username}")
    print(f"   Пароль: {'*' * len(password)}")
    print()
    print("ℹ️  Перезапустите сервер для применения изменений")
    return True

def toggle_basic_auth():
    """Включить/выключить Basic Auth."""
    env_path = ".env"
    if not os.path.exists(env_path):
        print("❌ Файл .env не найден")
        return
    
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Найти состояние
    enabled = False
    for line in lines:
        if line.strip().startswith('BASIC_AUTH_ENABLED'):
            enabled = line.strip().split('=')[1].lower() == 'true'
            break
    
    # Переключить состояние
    new_state = not enabled
    
    for i, line in enumerate(lines):
        if line.strip().startswith('BASIC_AUTH_ENABLED'):
            lines[i] = f"BASIC_AUTH_ENABLED={'true' if new_state else 'false'}\n"
            break
    
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Basic Authentication {'включена' if new_state else 'отключена'}")
    print("ℹ️  Перезапустите сервер для применения изменений")

def main():
    if len(sys.argv) < 2:
        print("🔐 Управление Basic Authentication")
        print()
        print("Команды:")
        print("  status           - показать текущие настройки")
        print("  change           - изменить логин и пароль (интерактивно)")
        print("  change <user> <pass> - изменить логин и пароль")
        print("  toggle           - включить/выключить Basic Auth")
        print("  quick <pass>     - быстро сменить пароль (логин остается)")
        print()
        print("Примеры:")
        print("  python3 manage_basic_auth.py status")
        print("  python3 manage_basic_auth.py change admin newpassword123")
        print("  python3 manage_basic_auth.py quick mysecretpass")
        print("  python3 manage_basic_auth.py toggle")
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        show_current_settings()
        
    elif command == "change":
        if len(sys.argv) >= 4:
            username = sys.argv[2]
            password = sys.argv[3]
            change_credentials(username, password)
        else:
            change_credentials()
            
    elif command == "quick":
        if len(sys.argv) >= 3:
            # Получаем текущий username
            current_user = "admin"  # по умолчанию
            env_path = ".env"
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('BASIC_AUTH_USERNAME='):
                            current_user = line.strip().split('=', 1)[1]
                            break
            
            new_password = sys.argv[2]
            change_credentials(current_user, new_password)
        else:
            print("❌ Укажите новый пароль")
            print("Пример: python3 manage_basic_auth.py quick newpassword")
            
    elif command == "toggle":
        toggle_basic_auth()
        
    else:
        print(f"❌ Неизвестная команда: {command}")

if __name__ == "__main__":
    main()