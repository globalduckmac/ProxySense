#!/usr/bin/env python3
"""
Скрипт исправления проблемы авторизации на сервере
Исправляет проблему с cookie и secure настройками
"""

import os

# Файлы для исправления
files_to_fix = [
    '/opt/reverse-proxy-monitor/backend/ui/routes.py'
]

def fix_cookie_settings():
    """Исправляет настройки cookie для работы через Nginx proxy"""
    
    routes_file = '/opt/reverse-proxy-monitor/backend/ui/routes.py'
    
    # Читаем файл
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Находим и исправляем настройки cookie
    old_cookie_code = '''    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEBUG
    )'''
    
    new_cookie_code = '''    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,
        samesite='lax'
    )'''
    
    if old_cookie_code in content:
        content = content.replace(old_cookie_code, new_cookie_code)
        
        # Записываем исправленный файл
        with open(routes_file, 'w') as f:
            f.write(content)
        
        print("✅ Исправлены настройки cookie в routes.py")
        return True
    else:
        print("⚠️ Код cookie не найден для исправления")
        return False

def add_debug_logging():
    """Добавляет отладочные логи для диагностики"""
    
    routes_file = '/opt/reverse-proxy-monitor/backend/ui/routes.py'
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Добавляем отладку в функцию get_current_user_optional
    debug_code = '''def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
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
        return result
    except Exception as e:
        logger.error(f"Error in get_current_user_optional: {e}")
        return None'''
    
    # Ищем существующую функцию
    old_function_start = 'def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:'
    
    if old_function_start in content:
        # Находим конец функции
        start_pos = content.find(old_function_start)
        if start_pos != -1:
            # Находим следующую функцию или @router
            end_markers = ['\n\n@router', '\n\nasync def', '\n\ndef ']
            end_pos = len(content)
            
            for marker in end_markers:
                marker_pos = content.find(marker, start_pos + 100)  # ищем после начала функции
                if marker_pos != -1 and marker_pos < end_pos:
                    end_pos = marker_pos
            
            # Заменяем функцию
            old_function = content[start_pos:end_pos]
            content = content.replace(old_function, debug_code + '\n\n')
            
            with open(routes_file, 'w') as f:
                f.write(content)
            
            print("✅ Добавлена отладочная информация в get_current_user_optional")
            return True
    
    print("⚠️ Функция get_current_user_optional не найдена для исправления")
    return False

def restart_service():
    """Перезапускает сервис"""
    os.system("systemctl restart reverse-proxy-monitor")
    print("✅ Сервис перезапущен")

if __name__ == "__main__":
    print("🔧 Исправление проблем авторизации...")
    
    cookie_fixed = fix_cookie_settings()
    debug_added = add_debug_logging()
    
    if cookie_fixed or debug_added:
        print("\n🔄 Перезапуск сервиса...")
        restart_service()
        print("\n✅ Исправления применены! Попробуйте войти снова.")
    else:
        print("\n⚠️ Никаких изменений не внесено")