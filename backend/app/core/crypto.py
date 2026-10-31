import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings


def _get_fernet() -> Fernet:
    """Derive deterministic 32-byte Fernet key from application SECRET_KEY."""
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_secret(plain_text: str) -> str:
    """Encrypt sensitive data (e.g., reset tokens) before storing in the database."""
    return _get_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """Decrypt sensitive data retrieved from database storage."""
    return _get_fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")

