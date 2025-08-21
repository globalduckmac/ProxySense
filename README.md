# Reverse Proxy & Monitor

Комплексная система мониторинга серверов и управления доменами с веб-интерфейсом на базе FastAPI.

## 🚀 Быстрая установка

### Автоматическая установка на Ubuntu 22.04

#### Вариант 1: Полная установка (рекомендуется)
```bash
# Загрузка и запуск полного скрипта установки
wget https://raw.githubusercontent.com/globalduckmac/ProxySense/main/deploy_fixed.sh
chmod +x deploy_fixed.sh
sudo ./deploy_fixed.sh
```

#### Вариант 2: Быстрая установка
```bash
# Минимальная установка с основными исправлениями
wget https://raw.githubusercontent.com/globalduckmac/ProxySense/main/deploy_simple.sh
chmod +x deploy_simple.sh
sudo ./deploy_simple.sh
```

#### Вариант 3: Исправление ошибок production
```bash
# Если у вас ошибки Pydantic или базы данных
cd /opt/reverse-proxy-monitor
wget https://raw.githubusercontent.com/globalduckmac/ProxySense/main/fix_production_errors.sh
chmod +x fix_production_errors.sh
sudo ./fix_production_errors.sh
```

Все скрипты работают на Ubuntu 22.04+ и включают исправления известных проблем.

## ✨ Возможности

- **Мониторинг серверов** - отслеживание ресурсов через Glances API
- **Управление доменами** - автоматическая проверка NS записей
- **SSH управление** - подключение и управление серверами через SSH
- **Nginx конфигурация** - автоматическое создание конфигов с SSL
- **Telegram уведомления** - мгновенные алерты о проблемах
- **Веб-интерфейс** - современный UI для управления всеми компонентами
- **Управление пользователями** - система ролей и прав доступа

## 🔧 Первая настройка

1. **Войти в систему**:
   - URL: `http://your-domain.com` или `http://your-ip:5000`
   - Логин: `admin`
   - Пароль: `admin123`

2. **Обязательно сменить пароль** после первого входа

3. **Настроить Telegram** (опционально):
   ```bash
   nano /opt/reverse-proxy-monitor/.env
   # Добавить:
   # TELEGRAM_BOT_TOKEN=your_bot_token
   # TELEGRAM_CHAT_ID=your_chat_id
   ```

4. **Настроить SSL** (если указан домен):
   ```bash
   apt install certbot python3-certbot-nginx
   certbot --nginx -d your-domain.com
   ```

## 📊 Управление

### Статус сервиса
```bash
systemctl status reverse-proxy-monitor
```

### Логи
```bash
journalctl -u reverse-proxy-monitor -f
```

### Перезапуск
```bash
systemctl restart reverse-proxy-monitor
```

### Обновление
```bash
su -c '/opt/reverse-proxy-monitor/update.sh' rpmonitor
```

## 🏗️ Архитектура

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Frontend**: Jinja2 templates + Vanilla JavaScript
- **Мониторинг**: APScheduler + Glances API
- **Безопасность**: JWT + bcrypt + роли пользователей
- **Развертывание**: Systemd + Nginx + UFW

## 📝 Конфигурация

Основные настройки в файле `/opt/reverse-proxy-monitor/.env`:

```env
# База данных
DATABASE_URL=postgresql://user:pass@localhost/db

# Безопасность
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret

# Приложение
HOST=0.0.0.0
PORT=5000

# Telegram (опционально)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 🔍 Устранение неполадок

### Типичные ошибки и решения

#### 1. Ошибки Pydantic validation
**Ошибка**: `Extra inputs are not permitted` для JWT_SECRET_KEY, ENCRYPTION_KEY
**Решение**: Используйте `fix_production_errors.sh`

#### 2. Синтаксические ошибки в database.py  
**Ошибка**: `SyntaxError: invalid syntax` в backend/database.py
**Решение**: Скрипт исправляет конфигурацию пула БД

#### 3. Все роуты возвращают 404
**Ошибка**: 404 Not Found для всех страниц
**Решение**: Исправление регистрации роутеров в main.py

#### 4. Проблемы с аутентификацией  
**Ошибка**: Не работает вход за reverse proxy
**Решение**: Исправление настроек cookie на `secure=False`

### Диагностические команды

#### Сервис не запускается
```bash
journalctl -u reverse-proxy-monitor --no-pager -n 20
systemctl status reverse-proxy-monitor
```

#### Проверка портов
```bash
ss -tlnp | grep :5000
ufw status
curl -I http://localhost:5000/
```

#### Тест базы данных
```bash
cd /opt/reverse-proxy-monitor
source venv/bin/activate
python3 -c "from backend.database import engine; print('DB OK' if engine else 'DB Error')"
```

## 📚 Документация

Подробная документация доступна в файле [install.md](install.md).

## 🔄 Обновления

Система автоматически создает скрипт обновления, который:
- Создает резервную копию
- Обновляет код из Git
- Устанавливает новые зависимости
- Применяет миграции БД
- Перезапускает сервис

## 🛡️ Безопасность

- Приложение работает от отдельного пользователя `rpmonitor`
- Настроен UFW файрвол
- Пароли хэшируются bcrypt
- JWT токены для аутентификации
- Роли пользователей (admin/user)

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи сервиса
2. Убедитесь что все зависимости установлены
3. Проверьте конфигурацию `.env`
4. Проверьте статус PostgreSQL (если используется)

---

**Важно**: После установки обязательно смените пароль администратора и настройте SSL сертификат для продакшена!