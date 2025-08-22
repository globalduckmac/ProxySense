"""
Middleware для HTTP Basic Authentication.
"""
import base64
import secrets
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from backend.config import settings


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для базовой HTTP аутентификации.
    Защищает все маршруты кроме статических файлов.
    """
    
    def __init__(self, app, username: Optional[str] = None, password: Optional[str] = None):
        super().__init__(app)
        self.username = username or settings.BASIC_AUTH_USERNAME
        self.password = password or settings.BASIC_AUTH_PASSWORD
        self.enabled = settings.BASIC_AUTH_ENABLED
        
    async def dispatch(self, request: Request, call_next):
        # Пропускаем если Basic Auth отключен
        if not self.enabled:
            return await call_next(request)
            
        # Пропускаем статические файлы
        if request.url.path.startswith('/static/'):
            return await call_next(request)
            
        # Проверяем Basic Auth
        if not self._is_authenticated(request):
            return self._auth_required_response()
            
        return await call_next(request)
    
    def _is_authenticated(self, request: Request) -> bool:
        """Проверить Basic Auth заголовки или JWT cookie."""
        # Сначала проверяем JWT cookie для authenticated пользователей
        if self._check_jwt_cookie(request):
            return True
            
        # Затем проверяем Basic Auth заголовки
        authorization = request.headers.get('Authorization')
        if not authorization:
            return False
            
        try:
            scheme, credentials = authorization.split(' ', 1)
            if scheme.lower() != 'basic':
                return False
                
            decoded = base64.b64decode(credentials).decode('utf-8')
            username, password = decoded.split(':', 1)
            
            # Используем secrets.compare_digest для защиты от timing атак
            username_correct = secrets.compare_digest(username, self.username)
            password_correct = secrets.compare_digest(password, self.password)
            
            return username_correct and password_correct
            
        except (ValueError, UnicodeDecodeError):
            return False
    
    def _check_jwt_cookie(self, request: Request) -> bool:
        """Проверить JWT токен в cookie."""
        try:
            from backend.auth import verify_token
            token = request.cookies.get("access_token")
            if token:
                username = verify_token(token)
                return username is not None
        except:
            pass
        return False
    
    def _auth_required_response(self) -> Response:
        """Вернуть ответ требующий аутентификацию."""
        return Response(
            content="Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic realm=\"Reverse Proxy Monitor\""}
        )


def create_basic_auth_middleware(username: Optional[str] = None, password: Optional[str] = None):
    """
    Создать middleware для Basic Auth.
    
    Args:
        username: Имя пользователя (по умолчанию из настроек)
        password: Пароль (по умолчанию из настроек)
    """
    def middleware(app):
        return BasicAuthMiddleware(app, username, password)
    return middleware