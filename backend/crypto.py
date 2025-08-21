"""
Cryptography utilities for encrypting sensitive data.
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional
import logging

from backend.config import settings

logger = logging.getLogger(__name__)


def generate_key() -> bytes:
    """Generate a new encryption key."""
    return Fernet.generate_key()


def save_key(key: bytes, path: Optional[str] = None) -> None:
    """Save encryption key to file."""
    key_path = Path(path or settings.ENCRYPTION_KEY_PATH)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key)
    os.chmod(key_path, 0o600)  # Restrict permissions


def load_key(path: Optional[str] = None) -> bytes:
    """Load encryption key from file."""
    key_path = Path(path or settings.ENCRYPTION_KEY_PATH)
    
    if not key_path.exists():
        logger.warning(f"Encryption key not found at {key_path}, generating new one")
        key = generate_key()
        save_key(key, path)
        return key
    
    with open(key_path, "rb") as f:
        return f.read()


def get_cipher() -> Fernet:
    """Get Fernet cipher instance."""
    key = load_key()
    return Fernet(key)


def encrypt_string(plaintext: str) -> bytes:
    """Encrypt a string."""
    if not plaintext:
        return b""
    
    cipher = get_cipher()
    return cipher.encrypt(plaintext.encode())


def decrypt_string(ciphertext: bytes) -> str:
    """Decrypt bytes to string."""
    if not ciphertext:
        return ""
    
    cipher = get_cipher()
    return cipher.decrypt(ciphertext).decode()


def encrypt_if_needed(value: Optional[str]) -> Optional[bytes]:
    """Encrypt a value if it exists."""
    if value is None:
        return None
    return encrypt_string(value)


def decrypt_if_needed(value: Optional[bytes]) -> Optional[str]:
    """Decrypt a value if it exists."""
    if value is None:
        return None
    return decrypt_string(value)
