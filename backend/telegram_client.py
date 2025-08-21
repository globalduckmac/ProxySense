"""
Telegram Bot API client for sending notifications.
"""
import httpx
import asyncio
from typing import Optional
import logging

from backend.config import settings
from backend.models import Alert

logger = logging.getLogger(__name__)


class TelegramClient:
    """Client for sending messages via Telegram Bot API."""
    
    def __init__(self):
        # Settings will be loaded dynamically when needed
        self.bot_token = None
        self.chat_id = None
        self.base_url = None
    
    async def _load_settings(self):
        """Load Telegram settings from environment variables."""
        try:
            import os
            
            # Load from environment variables first
            self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            # If not found in environment, try database (fallback)
            if not self.bot_token or not self.chat_id:
                try:
                    from backend.database import SessionLocal
                    from backend.models import Setting
                    from backend.crypto import decrypt_if_needed
                    
                    with SessionLocal() as db:
                        if not self.bot_token:
                            bot_token_setting = db.query(Setting).filter(Setting.key == "telegram.bot_token").first()
                            if bot_token_setting and bot_token_setting.value:
                                self.bot_token = decrypt_if_needed(bot_token_setting.value)
                        
                        if not self.chat_id:
                            chat_id_setting = db.query(Setting).filter(Setting.key == "telegram.chat_id").first()
                            if chat_id_setting and chat_id_setting.value:
                                self.chat_id = decrypt_if_needed(chat_id_setting.value)
                except Exception as db_error:
                    logger.warning(f"Failed to load Telegram settings from database: {db_error}")
            
            if self.bot_token:
                self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
            else:
                self.base_url = None
                logger.warning("TELEGRAM_BOT_TOKEN not found in environment variables")
                
            if not self.chat_id:
                logger.warning("TELEGRAM_CHAT_ID not found in environment variables")
                    
        except Exception as e:
            logger.error(f"Failed to load Telegram settings: {e}")
            self.bot_token = None
            self.chat_id = None
            self.base_url = None
    
    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a message to the configured chat."""
        # Always reload settings before sending
        await self._load_settings()
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot token or chat ID not configured")
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode
                    }
                )
                
                if response.status_code == 200:
                    logger.info("Message sent to Telegram successfully")
                    return True
                else:
                    logger.error(f"Failed to send Telegram message: {response.status_code} {response.text}")
                    return False
        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send an alert notification to Telegram."""
        # Always reload settings before sending
        await self._load_settings()
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram settings not configured for alert")
            return False
        
        # Format alert message (using HTML instead of Markdown)
        level_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }
        
        emoji = level_emoji.get(alert.level.value, "📢")
        
        # Escape HTML characters in message content
        import html
        safe_title = html.escape(alert.title)
        safe_message = html.escape(alert.message)
        safe_type = html.escape(alert.alert_type)
        
        message = f"{emoji} <b>{safe_title}</b>\n\n"
        message += f"{safe_message}\n\n"
        message += f"<b>Level:</b> {alert.level.value.upper()}\n"
        message += f"<b>Type:</b> {safe_type}\n"
        message += f"<b>Time:</b> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return await self.send_message(message, parse_mode="HTML")
    
    async def send_server_down_alert(self, server_name: str, server_host: str, failure_count: int) -> bool:
        """Send server down alert."""
        message = f"🚨 *Server Down Alert*\n\n"
        message += f"Server *{server_name}* ({server_host}) is unreachable.\n"
        message += f"Failed {failure_count} consecutive health checks.\n\n"
        message += f"Please check the server status immediately."
        
        return await self.send_message(message)
    
    async def send_server_recovered_alert(self, server_name: str, server_host: str) -> bool:
        """Send server recovery alert."""
        message = f"✅ *Server Recovered*\n\n"
        message += f"Server *{server_name}* ({server_host}) is now responding.\n"
        message += f"Service has been restored."
        
        return await self.send_message(message)
    
    async def send_ssl_error_alert(self, domain: str, error: str) -> bool:
        """Send SSL certificate error alert."""
        message = f"🔒 *SSL Certificate Error*\n\n"
        message += f"Domain: *{domain}*\n"
        message += f"Error: {error}\n\n"
        message += f"Please check the SSL certificate configuration."
        
        return await self.send_message(message)
    
    async def send_deployment_error_alert(self, target: str, error: str) -> bool:
        """Send deployment error alert."""
        message = f"⚙️ *Deployment Error*\n\n"
        message += f"Target: *{target}*\n"
        message += f"Error: {error}\n\n"
        message += f"Please check the deployment logs."
        
        return await self.send_message(message)
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test Telegram bot connection."""
        # Always reload settings before testing
        await self._load_settings()
        
        if not self.bot_token:
            return False, "Bot token not configured"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/getMe")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        bot_name = bot_info.get("first_name", "Unknown")
                        return True, f"Connected to bot: {bot_name}"
                    else:
                        return False, f"API error: {data.get('description', 'Unknown error')}"
                else:
                    return False, f"HTTP {response.status_code}: {response.text}"
        
        except Exception as e:
            return False, f"Connection error: {str(e)}"
