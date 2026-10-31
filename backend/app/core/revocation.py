import threading
import time
from typing import Dict, Optional
from jose import jwt

from app.core.config import settings

# Thread-safe in-memory cache of revoked JWT IDs (jti -> expiry_timestamp)
_revoked_tokens: Dict[str, float] = {}
_lock = threading.Lock()


def _get_redis_client():
    try:
        import redis
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        client.ping()
        return client
    except Exception:
        return None


def revoke_token(token_str: str) -> None:
    """
    Revoke a JWT token server-side before its natural expiration.
    Extracts the unique 'jti' (JWT ID) and records it with a TTL matching
    the token's remaining validity period.
    """
    try:
        # Decode without verifying signature since it was already authenticated
        payload = jwt.decode(
            token_str,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return

        now = time.time()
        ttl = int(exp - now)
        if ttl <= 0:
            return  # Already expired, no need to store

        # 1. In-memory store
        with _lock:
            # Clean up expired items periodically
            expired_keys = [k for k, exp_time in _revoked_tokens.items() if exp_time <= now]
            for k in expired_keys:
                _revoked_tokens.pop(k, None)
            _revoked_tokens[jti] = exp

        # 2. Redis distributed store if available
        r = _get_redis_client()
        if r is not None:
            try:
                r.setex(f"revoked_jwt:{jti}", ttl, "1")
            except Exception:
                pass
    except Exception:
        pass


def is_token_revoked(token_str: str) -> bool:
    """
    Check if a JWT token has been explicitly revoked server-side.
    """
    try:
        payload = jwt.decode(
            token_str,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
        jti = payload.get("jti")
        if not jti:
            return False

        now = time.time()

        # 1. Check in-memory blacklist
        with _lock:
            if jti in _revoked_tokens:
                if _revoked_tokens[jti] > now:
                    return True
                else:
                    _revoked_tokens.pop(jti, None)

        # 2. Check Redis blacklist if available
        r = _get_redis_client()
        if r is not None:
            try:
                if r.exists(f"revoked_jwt:{jti}"):
                    return True
            except Exception:
                pass

        return False
    except Exception:
        return False


def reset_revocations() -> None:
    """Clear recorded revocations (useful for tests)."""
    with _lock:
        _revoked_tokens.clear()

