#!/usr/bin/env python3
"""
Скрипт исправления проблем с пулом соединений базы данных
Исправляет исчерпание QueuePool limit и timeout соединений
"""

import os

def fix_database_config():
    """Исправляет настройки пула соединений в database.py"""
    
    database_file = '/opt/reverse-proxy-monitor/backend/database.py'
    
    # Читаем файл
    with open(database_file, 'r') as f:
        content = f.read()
    
    # Находим и исправляем настройки пула соединений
    old_engine_config = '''engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300'''
    
    new_engine_config = '''engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60'''
    
    if old_engine_config in content:
        content = content.replace(old_engine_config, new_engine_config)
        
        with open(database_file, 'w') as f:
            f.write(content)
        
        print("✅ Исправлены настройки пула соединений в database.py")
        return True
    else:
        print("⚠️ Конфигурация engine не найдена для исправления")
        # Попробуем найти альтернативный вариант
        alt_config = '''engine = create_engine(settings.DATABASE_URL'''
        if alt_config in content:
            # Заменим всю строку создания engine
            import re
            pattern = r'engine = create_engine\([^)]*\)'
            replacement = '''engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60
)'''
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            
            with open(database_file, 'w') as f:
                f.write(content)
            
            print("✅ Исправлена альтернативная конфигурация engine")
            return True
        
        return False

def fix_session_management():
    """Исправляет управление сессиями в routes.py"""
    
    routes_file = '/opt/reverse-proxy-monitor/backend/ui/routes.py'
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Исправляем функцию get_current_user_optional для правильного закрытия сессий
    new_function = '''def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session, return None if not authenticated."""
    try:
        token = request.cookies.get("access_token")
        logger.info(f"Cookie access_token: {token is not None}")
        if not token:
            logger.info("No access_token cookie found")
            return None
        
        from backend.auth import verify_token
        username = verify_token(token)
        logger.info(f"Token verified, username: {username}")
        if not username:
            logger.info("Token verification failed")
            return None
        
        user = db.query(User).filter(User.username == username).first()
        result = user if user and user.is_active else None
        logger.info(f"User lookup result: {result is not None}")
        
        # Явно закрываем сессию после использования
        try:
            db.close()
        except:
            pass
            
        return result
    except Exception as e:
        logger.error(f"Error in get_current_user_optional: {e}")
        # Убеждаемся что сессия закрыта даже при ошибке
        try:
            db.close()
        except:
            pass
        return None'''
    
    # Ищем существующую функцию и заменяем
    import re
    pattern = r'def get_current_user_optional\(.*?\n(?:(?:    .*\n)*?)(?=\n\n@|\n\nasync def|\n\ndef |$)'
    
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(pattern, new_function, content, flags=re.MULTILINE | re.DOTALL)
        
        with open(routes_file, 'w') as f:
            f.write(content)
        
        print("✅ Исправлено управление сессиями в get_current_user_optional")
        return True
    else:
        print("⚠️ Функция get_current_user_optional не найдена")
        return False

def restart_service():
    """Перезапускает сервис"""
    os.system("systemctl restart reverse-proxy-monitor")
    print("✅ Сервис перезапущен")

if __name__ == "__main__":
    print("🔧 Исправление проблем с пулом соединений БД...")
    
    db_fixed = fix_database_config()
    session_fixed = fix_session_management()
    
    if db_fixed or session_fixed:
        print("\n🔄 Перезапуск сервиса...")
        restart_service()
        print("\n✅ Исправления применены!")
        print("Пул соединений увеличен до 20 + 30 overflow")
        print("Добавлено принудительное закрытие сессий")
    else:
        print("\n⚠️ Никаких изменений не внесено")