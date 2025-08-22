# Basic Authentication - Руководство

HTTP Basic Authentication добавляет дополнительный слой защиты перед основной JWT аутентификацией.

## 🔧 Быстрое управление

### Посмотреть текущие настройки
```bash
python3 manage_basic_auth.py status
```

### Изменить логин и пароль
```bash
# Интерактивно (спросит логин и пароль)
python3 manage_basic_auth.py change

# Сразу указать новые данные
python3 manage_basic_auth.py change newuser newpassword123
```

### Быстро сменить пароль (логин остается тот же)
```bash
python3 manage_basic_auth.py quick mynewpassword
```

### Включить/выключить Basic Auth
```bash
python3 manage_basic_auth.py toggle
```

## 📁 Управление через .env файл

Можно напрямую редактировать файл `.env`:

```env
# Basic Authentication Settings
BASIC_AUTH_ENABLED=true
BASIC_AUTH_USERNAME=yourusername
BASIC_AUTH_PASSWORD=yourpassword
```

После изменений перезапустите сервер.

## 🌐 Как это работает

1. **При включении** - все страницы (кроме `/static/*`) требуют Basic Auth
2. **Браузер показывает** стандартное окно ввода логина/пароля
3. **После успешного входа** - работает обычная JWT аутентификация
4. **Защита от атак** - используется `secrets.compare_digest()` против timing атак

## 🎯 Рекомендации по безопасности

- **Используйте сложные пароли** (минимум 12 символов)
- **Регулярно меняйте пароль** (раз в месяц)
- **Не используйте простые комбинации** типа admin/admin
- **В продакшене обязательно включайте HTTPS**

## 📋 Примеры использования

### Для разработки
```bash
python3 manage_basic_auth.py change dev devpassword123
```

### Для продакшена
```bash
python3 manage_basic_auth.py change prod $(openssl rand -base64 32)
```

### Временное отключение
```bash
python3 manage_basic_auth.py toggle  # выключить
# ... делаем что-то ...
python3 manage_basic_auth.py toggle  # включить обратно
```

## 🔍 Проверка работы

После настройки Basic Auth:

1. Откройте браузер и перейдите на главную страницу
2. Должно появиться окно аутентификации
3. Введите ваши учетные данные
4. После успешного входа откроется обычная страница входа в систему

## ⚠️ Важные моменты

- Basic Auth **не заменяет** основную аутентификацию - это дополнительный слой
- Статические файлы (CSS, JS, изображения) доступны без Basic Auth
- Изменения применяются только после перезапуска сервера
- В Replit сервер перезапускается автоматически при изменении файлов