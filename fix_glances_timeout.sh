#!/bin/bash

###############################################################################
# ИСПРАВЛЕНИЕ GLANCES TIMEOUT ПРОБЛЕМЫ
# Увеличивает таймауты и улучшает обработку ошибок
###############################################################################

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Проверка root
if [[ $EUID -ne 0 ]]; then
    error "Запустите скрипт с sudo"
fi

log "🔧 Исправление проблем с Glances..."

# Переходим в директорию приложения
cd /opt/reverse-proxy-monitor || error "Директория не найдена"

# Останавливаем сервис
log "Остановка сервиса..."
systemctl stop reverse-proxy-monitor

# Создаем бэкап оригинальных файлов
log "Создание бэкапов..."
cp backend/config.py backend/config.py.backup.$(date +%s)
cp backend/glances_client.py backend/glances_client.py.backup.$(date +%s)

# Обновляем config.py - увеличиваем таймаут Glances
log "Обновление таймаутов в config.py..."
sed -i 's/GLANCES_TIMEOUT: int = 10/GLANCES_TIMEOUT: int = 30  # Увеличен с 10 до 30 секунд/' backend/config.py

# Обновляем glances_client.py с улучшенной обработкой таймаутов
log "Обновление glances_client.py..."
cat > backend/glances_client.py << 'EOF'
"""
Glances API client for monitoring server metrics.
"""
import httpx
import asyncio
from typing import Optional, Dict, Any, Tuple
import logging

from backend.config import settings

logger = logging.getLogger(__name__)


class GlancesClient:
    """Client for interacting with Glances API."""
    
    def __init__(self):
        self.timeout = settings.GLANCES_TIMEOUT
    
    async def get_all_stats(self, url: str, auth: Optional[Tuple[str, str]] = None,
                           headers: Optional[Dict[str, str]] = None,
                           timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get all statistics from Glances API."""
        timeout = timeout or self.timeout
        
        try:
            # Создаем клиент с увеличенными таймаутами
            timeout_config = httpx.Timeout(
                connect=10.0,  # таймаут подключения
                read=timeout,   # таймаут чтения
                write=10.0,     # таймаут записи
                pool=10.0       # таймаут пула соединений
            )
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers={"User-Agent": "Reverse-Proxy-Monitor/1.0"}
            ) as client:
                
                logger.debug(f"Fetching Glances data from {url} with timeout {timeout}s")
                
                response = await client.get(
                    url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Successfully fetched Glances data from {url}, data size: {len(str(data))}")
                    return data
                else:
                    logger.warning(f"Glances API returned status {response.status_code}: {response.text[:200]}")
                    return None
        
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout while fetching Glances data from {url}: {str(e)}")
            return None
        except httpx.ConnectError as e:
            logger.warning(f"Connection error while fetching Glances data from {url}: {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error while fetching Glances data from {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching Glances data from {url}: {e}")
            return None
    
    async def get_cpu_stats(self, url: str, auth: Optional[Tuple[str, str]] = None,
                           headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Get CPU statistics from Glances API."""
        try:
            cpu_url = url.replace("/api/4/all", "/api/4/cpu")
            
            timeout_config = httpx.Timeout(
                connect=10.0,
                read=self.timeout,
                write=10.0,
                pool=10.0
            )
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                headers={"User-Agent": "Reverse-Proxy-Monitor/1.0"}
            ) as client:
                response = await client.get(
                    cpu_url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get CPU stats: {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"Error fetching CPU stats: {e}")
            return None
    
    async def get_memory_stats(self, url: str, auth: Optional[Tuple[str, str]] = None,
                              headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Get memory statistics from Glances API."""
        try:
            memory_url = url.replace("/api/4/all", "/api/4/mem")
            
            timeout_config = httpx.Timeout(
                connect=10.0,
                read=self.timeout,
                write=10.0,
                pool=10.0
            )
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                headers={"User-Agent": "Reverse-Proxy-Monitor/1.0"}
            ) as client:
                response = await client.get(
                    memory_url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get memory stats: {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"Error fetching memory stats: {e}")
            return None
    
    async def get_disk_stats(self, url: str, auth: Optional[Tuple[str, str]] = None,
                            headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Get disk statistics from Glances API."""
        try:
            disk_url = url.replace("/api/4/all", "/api/4/fs")
            
            timeout_config = httpx.Timeout(
                connect=10.0,
                read=self.timeout,
                write=10.0,
                pool=10.0
            )
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                headers={"User-Agent": "Reverse-Proxy-Monitor/1.0"}
            ) as client:
                response = await client.get(
                    disk_url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get disk stats: {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"Error fetching disk stats: {e}")
            return None

    async def test_connection(self, url: str, auth: Optional[Tuple[str, str]] = None,
                             headers: Optional[Dict[str, str]] = None) -> bool:
        """Test connection to Glances API."""
        try:
            # Простой тест подключения
            timeout_config = httpx.Timeout(
                connect=5.0,
                read=15.0,
                write=5.0,
                pool=5.0
            )
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                headers={"User-Agent": "Reverse-Proxy-Monitor/1.0"}
            ) as client:
                response = await client.get(
                    url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully connected to Glances API at {url}")
                    return True
                else:
                    logger.warning(f"Glances API test failed with status {response.status_code}")
                    return False
        
        except Exception as e:
            logger.error(f"Failed to test Glances connection: {e}")
            return False


# Global instance
glances_client = GlancesClient()
EOF

# Проверяем права доступа
log "Исправление прав доступа..."
chown -R rpmonitor:rpmonitor /opt/reverse-proxy-monitor/

# Запускаем сервис
log "Запуск сервиса..."
systemctl start reverse-proxy-monitor

# Ждем запуска
sleep 5

# Проверяем статус
if systemctl is-active --quiet reverse-proxy-monitor; then
    log "✅ Сервис успешно запущен с обновленными настройками Glances"
    
    # Показываем текущие настройки
    echo
    log "📋 Обновленные настройки:"
    echo "   GLANCES_TIMEOUT: 30 секунд (было 10)"
    echo "   Добавлены детальные таймауты подключения"
    echo "   Улучшена обработка ошибок"
    echo "   Добавлен User-Agent для лучшей совместимости"
    
    echo
    log "🌐 Протестируйте мониторинг:"
    echo "   1. Откройте панель серверов"
    echo "   2. Нажмите 'Мониторинг' для вашего сервера"
    echo "   3. Данные должны загружаться без ошибок таймаута"
    
    echo
    log "📊 Последние логи сервиса:"
    journalctl -u reverse-proxy-monitor -n 10 --no-pager
    
else
    error "❌ Сервис не запустился. Проверьте логи: sudo journalctl -u reverse-proxy-monitor -f"
fi

log "🎉 Исправление Glances таймаутов завершено!"