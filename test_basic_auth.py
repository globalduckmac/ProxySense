#!/usr/bin/env python3
"""
Тестирование Basic Authentication.
"""
import requests
import base64
import json

def test_basic_auth(base_url="http://localhost:5000", username="admin", password="secret"):
    """Тестировать Basic Auth."""
    
    print(f"🧪 Тестирование Basic Authentication на {base_url}")
    print(f"   Пользователь: {username}")
    print(f"   Пароль: {password}")
    print()
    
    # Тест 1: Запрос без аутентификации
    print("📋 Тест 1: Запрос без Basic Auth заголовков")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 401:
            print("✅ Правильно: получен 401 Unauthorized")
            print(f"   WWW-Authenticate: {response.headers.get('WWW-Authenticate', 'Отсутствует')}")
        else:
            print(f"❌ Ожидался 401, получен: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
    
    print()
    
    # Тест 2: Запрос с правильной аутентификацией
    print("📋 Тест 2: Запрос с правильными учетными данными")
    try:
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        
        response = requests.get(base_url, headers=headers, timeout=5)
        if response.status_code == 200:
            print("✅ Успешно: аутентификация прошла")
        elif response.status_code == 302:
            print("✅ Успешно: получен редирект (нормально для UI)")
        else:
            print(f"❌ Неожиданный код: {response.status_code}")
            print(f"   Ответ: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
    
    print()
    
    # Тест 3: Запрос с неправильным паролем
    print("📋 Тест 3: Запрос с неправильным паролем")
    try:
        wrong_credentials = base64.b64encode(f"{username}:wrongpassword".encode()).decode()
        headers = {"Authorization": f"Basic {wrong_credentials}"}
        
        response = requests.get(base_url, headers=headers, timeout=5)
        if response.status_code == 401:
            print("✅ Правильно: неверные данные отклонены")
        else:
            print(f"❌ Ожидался 401, получен: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
    
    print()
    
    # Тест 4: Статические файлы (должны проходить без auth)
    print("📋 Тест 4: Доступ к статическим файлам")
    try:
        response = requests.get(f"{base_url}/static/css/style.css", timeout=5)
        if response.status_code == 200:
            print("✅ Статические файлы доступны без аутентификации")
        elif response.status_code == 404:
            print("ℹ️  Статический файл не найден (нормально если файл не существует)")
        else:
            print(f"❌ Неожиданный код для статики: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Использование: python3 test_basic_auth.py <url> <username> <password>")
        print("Пример: python3 test_basic_auth.py http://localhost:5000 admin secret")
        sys.exit(1)
    
    url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    test_basic_auth(url, username, password)