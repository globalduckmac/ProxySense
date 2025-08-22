#!/bin/bash

###############################################################################
# ТЕСТ ИМПОРТОВ В ВИРТУАЛЬНОМ ОКРУЖЕНИИ
# Правильно тестирует все модули в venv
###############################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== ТЕСТ ИМПОРТОВ В ВИРТУАЛЬНОМ ОКРУЖЕНИИ ===${NC}\n"

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor || {
    echo -e "${RED}❌ Директория не найдена${NC}"
    exit 1
}

# Проверяем наличие виртуального окружения
if [[ ! -f "venv/bin/python" ]]; then
    echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
    exit 1
fi

# Тестируем импорты в виртуальном окружении
echo "Тестирование импортов через venv..."
sudo -u rpmonitor venv/bin/python << 'EOF'
import sys
print(f"Python: {sys.executable}")
print(f"Python версия: {sys.version}")
print()

modules_to_test = [
    'pydantic_settings',
    'sqlalchemy', 
    'fastapi',
    'uvicorn',
    'psycopg2',
    'cryptography',
    'paramiko',
    'httpx',
    'jinja2',
    'backend.config',
    'backend.database',
    'backend.models',
    'backend.app'
]

success_count = 0
total_count = len(modules_to_test)

for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}")
        success_count += 1
    except ImportError as e:
        print(f"❌ {module}: {e}")
    except Exception as e:
        print(f"⚠️  {module}: {e}")

print(f"\nРезультат: {success_count}/{total_count} модулей импортированы успешно")

if success_count == total_count:
    print("🎉 Все импорты работают корректно!")
    exit(0)
else:
    print("⚠️ Некоторые импорты не работают")
    exit(1)
EOF

echo
echo "=== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ==="
echo "Размер виртуального окружения:"
sudo du -sh /opt/reverse-proxy-monitor/venv/

echo
echo "Установленные пакеты:"
sudo -u rpmonitor /opt/reverse-proxy-monitor/venv/bin/pip list | head -20