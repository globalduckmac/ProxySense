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
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Successfully fetched Glances data from {url}")
                    return data
                else:
                    logger.warning(f"Glances API returned status {response.status_code}: {response.text}")
                    return None
        
        except httpx.TimeoutException:
            logger.warning(f"Timeout while fetching Glances data from {url}")
            return None
        except httpx.ConnectError:
            logger.warning(f"Connection error while fetching Glances data from {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Glances data from {url}: {e}")
            return None
    
    async def get_cpu_stats(self, url: str, auth: Optional[Tuple[str, str]] = None,
                           headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Get CPU statistics from Glances API."""
        try:
            cpu_url = url.replace("/api/4/all", "/api/4/cpu")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
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
            mem_url = url.replace("/api/4/all", "/api/4/mem")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    mem_url,
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
    
    async def test_connection(self, url: str, auth: Optional[Tuple[str, str]] = None,
                             headers: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """Test connection to Glances API."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    url,
                    auth=auth,
                    headers=headers or {}
                )
                
                if response.status_code == 200:
                    return True, "Connection successful"
                else:
                    return False, f"HTTP {response.status_code}: {response.text}"
        
        except httpx.TimeoutException:
            return False, "Connection timeout"
        except httpx.ConnectError:
            return False, "Connection refused"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
