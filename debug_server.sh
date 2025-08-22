#!/bin/bash

###############################################################################
# ДИАГНОСТИКА ПРОБЛЕМ С СЕРВЕРОМ
# Проверяет состояние приложения и выводит полезную информацию
###############################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== ДИАГНОСТИКА REVERSE PROXY MONITOR ===${NC}\n"

# 1. Проверка статуса сервиса
echo -e "${YELLOW}1. Статус systemd сервиса:${NC}"
sudo systemctl status reverse-proxy-monitor --no-pager -l

echo -e "\n${YELLOW}2. Последние логи сервиса:${NC}"
sudo journalctl -u reverse-proxy-monitor -n 20 --no-pager

echo -e "\n${YELLOW}3. Проверка портов:${NC}"
if command -v netstat >/dev/null 2>&1; then
    netstat -tlnp | grep :5000 || echo "Порт 5000 не занят"
    netstat -tlnp | grep :80 || echo "Порт 80 не занят"
    netstat -tlnp | grep :443 || echo "Порт 443 не занят"
else
    ss -tlnp | grep :5000 || echo "Порт 5000 не занят"
    ss -tlnp | grep :80 || echo "Порт 80 не занят"
    ss -tlnp | grep :443 || echo "Порт 443 не занят"
fi

echo -e "\n${YELLOW}4. Проверка процессов Python:${NC}"
ps aux | grep python | grep -v grep || echo "Процессы Python не найдены"

echo -e "\n${YELLOW}5. Проверка директории приложения:${NC}"
if [[ -d "/opt/reverse-proxy-monitor" ]]; then
    echo "✓ Директория существует"
    ls -la /opt/reverse-proxy-monitor/ | head -10
    echo "..."
    echo "Владелец файлов:"
    ls -la /opt/reverse-proxy-monitor/ | grep -E "(main.py|.env|venv)" || echo "Основные файлы не найдены"
else
    echo "✗ Директория /opt/reverse-proxy-monitor не найдена"
fi

echo -e "\n${YELLOW}6. Проверка .env файла:${NC}"
if [[ -f "/opt/reverse-proxy-monitor/.env" ]]; then
    echo "✓ .env файл существует"
    echo "Содержимое .env (без секретов):"
    grep -E "^(DEBUG|ENVIRONMENT|DATABASE_URL|BASIC_AUTH_ENABLED)" /opt/reverse-proxy-monitor/.env || echo "Основные переменные не найдены"
else
    echo "✗ .env файл не найден"
fi

echo -e "\n${YELLOW}7. Проверка базы данных PostgreSQL:${NC}"
sudo systemctl status postgresql --no-pager | head -3
sudo -u postgres psql -c "\l" | grep reverse_proxy_monitor || echo "БД не найдена"

echo -e "\n${YELLOW}8. Проверка Nginx:${NC}"
sudo systemctl status nginx --no-pager | head -3
if [[ -f "/etc/nginx/sites-enabled/reverse-proxy-monitor" ]]; then
    echo "✓ Конфигурация Nginx найдена"
else
    echo "✗ Конфигурация Nginx не найдена"
fi

echo -e "\n${YELLOW}9. Ручной запуск для диагностики:${NC}"
echo "Попытка ручного запуска приложения..."
if [[ -d "/opt/reverse-proxy-monitor" ]]; then
    cd /opt/reverse-proxy-monitor
    if [[ -f "venv/bin/python" ]]; then
        echo "Попытка запуска через виртуальное окружение..."
        timeout 10s sudo -u rpmonitor venv/bin/python main.py 2>&1 | head -20 || echo "Запуск прерван/завершен"
    else
        echo "✗ Виртуальное окружение не найдено"
    fi
else
    echo "✗ Не могу перейти в директорию приложения"
fi

echo -e "\n${YELLOW}10. Проверка файрвола (UFW):${NC}"
if command -v ufw >/dev/null 2>&1; then
    sudo ufw status || echo "UFW не настроен"
else
    echo "UFW не установлен"
fi

echo -e "\n${GREEN}=== КОНЕЦ ДИАГНОСТИКИ ===${NC}"
echo -e "\n${YELLOW}Рекомендации:${NC}"
echo "- Если сервис не активен: sudo systemctl start reverse-proxy-monitor"
echo "- Если есть ошибки в логах: sudo journalctl -u reverse-proxy-monitor -f"
echo "- Если порт 5000 не слушается: проверить запуск приложения"
echo "- Если Nginx не работает: sudo systemctl restart nginx"