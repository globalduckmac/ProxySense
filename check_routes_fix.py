#!/usr/bin/env python3
"""
Проверка и исправление backend/ui/routes.py
"""

import os

def check_and_fix_routes():
    """Проверяет и исправляет routes.py"""
    
    routes_file = '/opt/reverse-proxy-monitor/backend/ui/routes.py'
    
    if not os.path.exists(routes_file):
        print("❌ backend/ui/routes.py не найден!")
        return False
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Проверяем наличие основного маршрута
    if '@router.get("/")' not in content:
        print("⚠️ Основной маршрут / отсутствует")
        
        # Добавляем основной маршрут если его нет
        router_creation = 'router = APIRouter()'
        if router_creation in content:
            # Найдем место после создания router
            pos = content.find(router_creation) + len(router_creation)
            
            # Добавим основной маршрут
            main_route = '''


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: Session = Depends(get_db)
):
    """Main dashboard page."""
    # Простая проверка авторизации через cookie
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # Проверяем токен
    from backend.auth import verify_token
    username = verify_token(token)
    if not username:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # Получаем пользователя
    from backend.models import User
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # Простая статистика
    from backend.models import Server, Domain, Alert
    from sqlalchemy import func
    
    total_servers = db.query(func.count(Server.id)).scalar() or 0
    total_domains = db.query(func.count(Domain.id)).scalar() or 0
    unresolved_alerts = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False).scalar() or 0
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": user,
        "stats": {
            "total_servers": total_servers,
            "online_servers": 0,
            "total_domains": total_domains,
            "ssl_domains": 0,
            "unresolved_alerts": unresolved_alerts
        },
        "recent_tasks": [],
        "recent_alerts": []
    })'''
            
            new_content = content[:pos] + main_route + content[pos:]
            
            with open(routes_file, 'w') as f:
                f.write(new_content)
            
            print("✅ Добавлен основной маршрут /")
            return True
        else:
            print("❌ Не найден APIRouter() для добавления маршрута")
            return False
    else:
        print("✅ Основной маршрут / уже существует")
        return True

if __name__ == "__main__":
    print("🔧 Проверка и исправление routes.py...")
    
    if check_and_fix_routes():
        print("\n🔄 Перезапуск сервиса...")
        os.system("systemctl restart reverse-proxy-monitor")
        print("✅ Сервис перезапущен")
        
        print("\n📜 Проверка логов:")
        os.system("journalctl -u reverse-proxy-monitor --no-pager -n 10")
        
        print("\n🌐 Тестирование главной страницы...")
        os.system("curl -I http://localhost:5000/")
    else:
        print("❌ Не удалось исправить routes.py")