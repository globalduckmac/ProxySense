# Установка Reverse Proxy & Monitor

## Автоматическая установка

### Быстрая установка на Ubuntu 22.04

```bash
wget https://raw.githubusercontent.com/your-username/reverse-proxy-monitor/main/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

### Что делает скрипт:

1. **Обновляет систему** и устанавливает необходимые пакеты
2. **Устанавливает Python 3.11** из PPA
3. **Настраивает PostgreSQL** (опционально)
4. **Клонирует репозиторий** в выбранную директорию
5. **Создает пользователя** для приложения
6. **Устанавливает зависимости** Python
7. **Настраивает systemd сервис** для автозапуска
8. **Конфигурирует Nginx** (при указании домена)
9. **Настраивает файрвол** UFW
10. **Создает скрипт обновления**

### Настройки по умолчанию:

- **Пользователь**: `rpmonitor`
- **Директория**: `/opt/reverse-proxy-monitor`
- **Порт**: `5000`
- **База данных**: `rpmonitor`
- **Пользователь БД**: `rpmonitor`

### После установки:

1. **Доступ к приложению**: `http://your-domain.com` или `http://your-ip:5000`
2. **Логин**: `admin`
3. **Пароль**: `admin123`

⚠️ **Обязательно смените пароль после первого входа!**

## Управление сервисом

```bash
# Статус сервиса
sudo systemctl status reverse-proxy-monitor

# Перезапуск
sudo systemctl restart reverse-proxy-monitor

# Остановка
sudo systemctl stop reverse-proxy-monitor

# Запуск
sudo systemctl start reverse-proxy-monitor

# Логи
sudo journalctl -u reverse-proxy-monitor -f
```

## Обновление

```bash
sudo -u rpmonitor /opt/reverse-proxy-monitor/update.sh
```

## Ручная установка

### 1. Системные зависимости

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib nginx git supervisor
```

### 2. База данных

```bash
sudo -u postgres psql
CREATE DATABASE rpmonitor;
CREATE USER rpmonitor WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE rpmonitor TO rpmonitor;
\q
```

### 3. Приложение

```bash
sudo useradd -r -s /bin/bash -d /opt/reverse-proxy-monitor rpmonitor
sudo mkdir -p /opt/reverse-proxy-monitor
cd /opt/reverse-proxy-monitor
sudo git clone https://github.com/your-username/reverse-proxy-monitor.git .
sudo chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor

sudo -u rpmonitor python3.11 -m venv venv
sudo -u rpmonitor venv/bin/pip install -r setup_requirements.txt
```

### 4. Конфигурация

```bash
sudo -u rpmonitor cp .env.example .env
# Отредактируйте .env файл
```

### 5. Systemd сервис

```bash
sudo cp deploy/reverse-proxy-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable reverse-proxy-monitor
sudo systemctl start reverse-proxy-monitor
```

## SSL сертификат

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Настройка Telegram уведомлений

1. Создайте бота через @BotFather
2. Получите токен бота
3. Добавьте в `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```
4. Перезапустите сервис

## Мониторинг

### Логи приложения
```bash
tail -f /opt/reverse-proxy-monitor/logs/app.log
```

### Логи Nginx
```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Логи системы
```bash
sudo journalctl -u reverse-proxy-monitor -f
```

## Резервное копирование

### База данных
```bash
pg_dump -U rpmonitor -h localhost rpmonitor > backup.sql
```

### Файлы приложения
```bash
tar -czf rpmonitor-backup-$(date +%Y%m%d).tar.gz /opt/reverse-proxy-monitor
```

## Устранение неполадок

### Сервис не запускается
```bash
sudo journalctl -u reverse-proxy-monitor --no-pager -n 50
```

### Проблемы с базой данных
```bash
sudo -u rpmonitor /opt/reverse-proxy-monitor/venv/bin/python manage.py check-db
```

### Проблемы с портами
```bash
sudo netstat -tulpn | grep :5000
sudo ufw status
```

### Проверка конфигурации Nginx
```bash
sudo nginx -t
sudo systemctl reload nginx
```