# 🚀 Инструкция по развертыванию

## Быстрое развертывание

### 1. Скачайте и запустите скрипт развертывания:

```bash
# Рекомендуемый (полный) скрипт:
wget https://raw.githubusercontent.com/globalduckmac/ProxySense/main/deploy_fixed.sh
chmod +x deploy_fixed.sh
sudo ./deploy_fixed.sh

# Или упрощенный скрипт (только Ubuntu):
wget https://raw.githubusercontent.com/globalduckmac/ProxySense/main/deploy_simple.sh
chmod +x deploy_simple.sh
sudo ./deploy_simple.sh
```

### 2. После установки:

**Доступ к приложению:**
- URL: `http://your-server-ip`
- Логин: `admin`
- Пароль: `admin123`

## 🔐 Basic HTTP Authentication

По умолчанию Basic Auth **отключен**. Для включения дополнительной защиты:

### Включение Basic Auth:

```bash
# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor

# Включаем Basic Auth
python3 manage_basic_auth.py --enable --username your_username --password your_password

# Или интерактивно
python3 manage_basic_auth.py --enable
```

### Отключение Basic Auth:

```bash
python3 manage_basic_auth.py --disable
```

### Изменение credentials:

```bash
python3 manage_basic_auth.py --change-password
```

## 📋 Что включает скрипт развертывания:

✅ **Системные компоненты:**
- Python 3.11
- PostgreSQL база данных
- Nginx reverse proxy
- Systemd сервис

✅ **Исправления и оптимизации:**
- Увеличенный пул соединений БД (20+30)
- Cookie настройки для reverse proxy
- Корректная регистрация API роутов
- Автоматическое создание admin пользователя

✅ **Безопасность:**
- JWT токены
- Шифрование данных
- Опциональный Basic HTTP Auth
- Правильные права доступа

✅ **Мониторинг:**
- Systemd сервис с автозапуском
- Логирование в журнал
- Проверка состояния сервисов

## 🔧 Управление сервисом:

```bash
# Статус сервиса
sudo systemctl status reverse-proxy-monitor

# Перезапуск
sudo systemctl restart reverse-proxy-monitor

# Логи
sudo journalctl -u reverse-proxy-monitor -f

# Остановка/запуск
sudo systemctl stop reverse-proxy-monitor
sudo systemctl start reverse-proxy-monitor
```

## 🌐 Настройка Nginx:

Nginx автоматически настраивается для проксирования на порт 5000.
Конфигурация находится в `/etc/nginx/sites-enabled/reverse-proxy-monitor`

## ⚠️ Troubleshooting:

### Если приложение не запускается:
```bash
# Проверить логи
sudo journalctl -u reverse-proxy-monitor -n 50

# Проверить статус БД
sudo systemctl status postgresql

# Ручной запуск для диагностики
cd /opt/reverse-proxy-monitor
sudo -u rpmonitor venv/bin/python main.py
```

### Если Basic Auth не работает:
```bash
# Проверить настройки в .env
grep BASIC_AUTH /opt/reverse-proxy-monitor/.env

# Перезапустить сервис после изменений
sudo systemctl restart reverse-proxy-monitor
```

## 📞 Поддержка:

При проблемах с развертыванием проверьте:
1. Права доступа к файлам
2. Статус PostgreSQL
3. Логи сервиса
4. Конфигурацию Nginx