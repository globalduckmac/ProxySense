"""
Settings management API endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from backend.database import get_db
from backend.models import Setting, User
from backend.auth import get_admin_user, get_current_user_from_cookie
from backend.crypto import encrypt_if_needed, decrypt_if_needed
from backend.telegram_client import TelegramClient
from backend.config import settings as app_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class SettingCreate(BaseModel):
    key: str
    value: str
    is_encrypted: bool = False
    description: Optional[str] = None


class SettingUpdate(BaseModel):
    value: Optional[str] = None
    is_encrypted: Optional[bool] = None
    description: Optional[str] = None


class SettingResponse(BaseModel):
    id: int
    key: str
    value: Optional[str]  # Will be masked for encrypted values
    is_encrypted: bool
    description: Optional[str]
    updated_at: str
    
    class Config:
        from_attributes = True


class TelegramSettingsUpdate(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


class TelegramTestResponse(BaseModel):
    success: bool
    message: str


# Predefined settings with their default configurations
PREDEFINED_SETTINGS = {
    "telegram.bot_token": {
        "description": "Telegram Bot API Token",
        "is_encrypted": True,
        "default": ""
    },
    "telegram.chat_id": {
        "description": "Telegram Chat ID for notifications",
        "is_encrypted": False,
        "default": ""
    },
    "glances.poll_interval": {
        "description": "Glances polling interval in seconds",
        "is_encrypted": False,
        "default": "60"
    },
    "glances.max_failures": {
        "description": "Maximum consecutive failures before marking server as unreachable",
        "is_encrypted": False,
        "default": "3"
    },
    "dns.timeout": {
        "description": "DNS query timeout in seconds",
        "is_encrypted": False,
        "default": "5"
    },
    "dns.servers": {
        "description": "DNS servers for queries (comma-separated)",
        "is_encrypted": False,
        "default": "8.8.8.8,1.1.1.1"
    },
    "ssh.timeout": {
        "description": "SSH operation timeout in seconds",
        "is_encrypted": False,
        "default": "30"
    },
    "alerts.cleanup_days": {
        "description": "Days to keep resolved alerts before cleanup",
        "is_encrypted": False,
        "default": "90"
    },
    "tasks.cleanup_days": {
        "description": "Days to keep completed tasks before cleanup",
        "is_encrypted": False,
        "default": "30"
    },
    "metrics.retention_days": {
        "description": "Days to keep server metrics",
        "is_encrypted": False,
        "default": "30"
    }
}


@router.get("/", response_model=List[SettingResponse])
async def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """List all settings."""
    settings = db.query(Setting).order_by(Setting.key).all()
    
    # Convert to response format, masking encrypted values
    response_settings = []
    for setting in settings:
        value = setting.value
        if setting.is_encrypted and value:
            # Mask encrypted values
            decrypted_value = decrypt_if_needed(value)
            masked_value = "*" * min(len(decrypted_value), 8) if decrypted_value else ""
        else:
            masked_value = decrypt_if_needed(value) if value else ""
        
        response_settings.append(SettingResponse(
            id=setting.id,
            key=setting.key,
            value=masked_value,
            is_encrypted=setting.is_encrypted,
            description=setting.description,
            updated_at=setting.updated_at.isoformat()
        ))
    
    return response_settings


@router.post("/", response_model=SettingResponse)
async def create_setting(
    setting_data: SettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Create a new setting."""
    # Check if setting already exists
    existing_setting = db.query(Setting).filter(Setting.key == setting_data.key).first()
    if existing_setting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setting with this key already exists"
        )
    
    # Encrypt value if needed
    value = encrypt_if_needed(setting_data.value) if setting_data.is_encrypted else setting_data.value.encode()
    
    # Create setting
    setting = Setting(
        key=setting_data.key,
        value=value,
        is_encrypted=setting_data.is_encrypted,
        description=setting_data.description
    )
    
    db.add(setting)
    db.commit()
    db.refresh(setting)
    
    logger.info(f"Setting {setting.key} created by user {current_user.username}")
    
    # Return with masked value for encrypted settings
    masked_value = "*" * 8 if setting_data.is_encrypted and setting_data.value else setting_data.value
    return SettingResponse(
        id=setting.id,
        key=setting.key,
        value=masked_value,
        is_encrypted=setting.is_encrypted,
        description=setting.description,
        updated_at=setting.updated_at.isoformat()
    )


@router.get("/{setting_id}", response_model=SettingResponse)
async def get_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get a specific setting."""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found"
        )
    
    # Mask encrypted values
    value = setting.value
    if setting.is_encrypted and value:
        decrypted_value = decrypt_if_needed(value)
        masked_value = "*" * min(len(decrypted_value), 8) if decrypted_value else ""
    else:
        masked_value = decrypt_if_needed(value) if value else ""
    
    return SettingResponse(
        id=setting.id,
        key=setting.key,
        value=masked_value,
        is_encrypted=setting.is_encrypted,
        description=setting.description,
        updated_at=setting.updated_at.isoformat()
    )


@router.put("/{setting_id}", response_model=SettingResponse)
async def update_setting(
    setting_id: int,
    setting_data: SettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Update a setting."""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found"
        )
    
    # Update fields
    if setting_data.value is not None:
        # Encrypt value if needed
        if setting_data.is_encrypted is not None:
            setting.is_encrypted = setting_data.is_encrypted
        
        if setting.is_encrypted:
            setting.value = encrypt_if_needed(setting_data.value)
        else:
            setting.value = setting_data.value.encode()
    
    if setting_data.description is not None:
        setting.description = setting_data.description
    
    db.commit()
    db.refresh(setting)
    
    logger.info(f"Setting {setting.key} updated by user {current_user.username}")
    
    # Return with masked value for encrypted settings
    masked_value = "*" * 8 if setting.is_encrypted and setting_data.value else setting_data.value or ""
    return SettingResponse(
        id=setting.id,
        key=setting.key,
        value=masked_value,
        is_encrypted=setting.is_encrypted,
        description=setting.description,
        updated_at=setting.updated_at.isoformat()
    )


@router.delete("/{setting_id}")
async def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Delete a setting."""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found"
        )
    
    setting_key = setting.key
    db.delete(setting)
    db.commit()
    
    logger.info(f"Setting {setting_key} deleted by user {current_user.username}")
    return {"message": "Setting deleted successfully"}


@router.post("/telegram/update")
async def update_telegram_settings(
    telegram_data: TelegramSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Update Telegram notification settings."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    updated_settings = []
    
    if telegram_data.bot_token is not None:
        # Update or create bot token setting
        setting = db.query(Setting).filter(Setting.key == "telegram.bot_token").first()
        if setting:
            setting.value = encrypt_if_needed(telegram_data.bot_token)
        else:
            setting = Setting(
                key="telegram.bot_token",
                value=encrypt_if_needed(telegram_data.bot_token),
                is_encrypted=True,
                description="Telegram Bot API Token"
            )
            db.add(setting)
        updated_settings.append("bot_token")
    
    if telegram_data.chat_id is not None:
        # Update or create chat ID setting
        setting = db.query(Setting).filter(Setting.key == "telegram.chat_id").first()
        if setting:
            setting.value = telegram_data.chat_id.encode()
        else:
            setting = Setting(
                key="telegram.chat_id",
                value=telegram_data.chat_id.encode(),
                is_encrypted=False,
                description="Telegram Chat ID for notifications"
            )
            db.add(setting)
        updated_settings.append("chat_id")
    
    db.commit()
    
    logger.info(f"Telegram settings updated: {', '.join(updated_settings)} by user {current_user.username}")
    
    return {
        "message": "Telegram settings updated successfully",
        "updated_settings": updated_settings
    }


@router.post("/telegram/test", response_model=TelegramTestResponse)
async def test_telegram_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Test Telegram bot connection and send a test message."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Get Telegram settings
        bot_token_setting = db.query(Setting).filter(Setting.key == "telegram.bot_token").first()
        chat_id_setting = db.query(Setting).filter(Setting.key == "telegram.chat_id").first()
        
        if not bot_token_setting or not bot_token_setting.value:
            return TelegramTestResponse(
                success=False,
                message="Telegram bot token not configured"
            )
        
        if not chat_id_setting or not chat_id_setting.value:
            return TelegramTestResponse(
                success=False,
                message="Telegram chat ID not configured"
            )
        
        # Decrypt bot token
        bot_token = decrypt_if_needed(bot_token_setting.value)
        chat_id = decrypt_if_needed(chat_id_setting.value)
        
        # Create temporary client with settings from database
        telegram_client = TelegramClient()
        telegram_client.bot_token = bot_token
        telegram_client.chat_id = chat_id
        telegram_client.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Test connection
        success, message = await telegram_client.test_connection()
        
        if success:
            # Send test message
            test_message = "🧪 **Test Message**\n\nThis is a test message from your Reverse Proxy & Monitor system.\n\nTelegram notifications are working correctly!"
            await telegram_client.send_message(test_message)
            
            return TelegramTestResponse(
                success=True,
                message="Telegram connection successful and test message sent"
            )
        else:
            return TelegramTestResponse(
                success=False,
                message=f"Telegram connection failed: {message}"
            )
    
    except Exception as e:
        logger.error(f"Error testing Telegram connection: {e}")
        return TelegramTestResponse(
            success=False,
            message=f"Test failed: {str(e)}"
        )


@router.post("/initialize-defaults")
async def initialize_default_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Initialize default settings if they don't exist."""
    created_settings = []
    
    for key, config in PREDEFINED_SETTINGS.items():
        # Check if setting already exists
        existing_setting = db.query(Setting).filter(Setting.key == key).first()
        if existing_setting:
            continue
        
        # Create default setting
        value = config["default"]
        if config["is_encrypted"] and value:
            encrypted_value = encrypt_if_needed(value)
        else:
            encrypted_value = value.encode() if value else b""
        
        setting = Setting(
            key=key,
            value=encrypted_value,
            is_encrypted=config["is_encrypted"],
            description=config["description"]
        )
        
        db.add(setting)
        created_settings.append(key)
    
    db.commit()
    
    logger.info(f"Initialized {len(created_settings)} default settings by user {current_user.username}")
    
    return {
        "message": f"Initialized {len(created_settings)} default settings",
        "created_settings": created_settings
    }


@router.get("/export/all")
async def export_settings(
    include_encrypted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Export all settings (optionally including encrypted values)."""
    settings = db.query(Setting).order_by(Setting.key).all()
    
    exported_settings = {}
    for setting in settings:
        if setting.is_encrypted and not include_encrypted:
            # Skip encrypted settings unless explicitly requested
            continue
        
        value = decrypt_if_needed(setting.value) if setting.value else ""
        exported_settings[setting.key] = {
            "value": value,
            "is_encrypted": setting.is_encrypted,
            "description": setting.description
        }
    
    logger.info(f"Settings exported by user {current_user.username} (encrypted: {include_encrypted})")
    
    return {
        "settings": exported_settings,
        "export_date": str(datetime.utcnow()),
        "includes_encrypted": include_encrypted
    }


def get_setting_value(db: Session, key: str, default: Any = None) -> Any:
    """Helper function to get a setting value."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting or not setting.value:
        return default
    
    value = decrypt_if_needed(setting.value)
    
    # Try to convert to appropriate type
    if key.endswith(('.timeout', '.interval', '.days', '.port', '.max_failures')):
        try:
            return int(value)
        except ValueError:
            return default
    elif key.endswith('.enabled'):
        return value.lower() in ('true', '1', 'yes', 'on')
    
    return value
