import time
import threading
import uuid
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status

from app.core.config import settings

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local cutoff = now - window

-- 1. Remove expired timestamps outside the sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- 2. Count current active attempts in window
local current_count = redis.call('ZCARD', key)

if current_count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_score = now
    if oldest and #oldest >= 2 then
        oldest_score = tonumber(oldest[2])
    end
    local retry_after = math.max(1, math.ceil(window - (now - oldest_score)))
    return {0, retry_after, current_count}
end

-- 3. Atomically record this attempt and refresh TTL
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window + 5))
return {1, 0, current_count + 1}
"""


class InMemoryRateLimiter:
    """
    In-memory sliding window rate limiter with strict thread-safe locking.
    Tracks timestamps per client key (IP address) within a configurable window.
    """
    def __init__(self, requests_limit: int = 5, window_seconds: int = 60, name: str = "Request"):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.name = name
        self.history: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            # Discard expired timestamps
            timestamps = [ts for ts in self.history[key] if ts > cutoff]
            if len(timestamps) >= self.requests_limit:
                oldest = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {self.name.lower()}. Maximum {self.requests_limit} attempts per {self.window_seconds} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)
            self.history[key] = timestamps

    def reset(self) -> None:
        """Clear recorded attempts."""
        with self._lock:
            self.history.clear()


class HybridRateLimiter:
    """
    Multi-instance Redis-backed sliding window rate limiter with in-memory fallback.
    Executes an atomic Lua script on Redis to eliminate check-then-act race conditions
    under concurrent requests across clustered application instances.
    """
    def __init__(self, requests_limit: int = 5, window_seconds: int = 60, name: str = "Request"):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.name = name
        self.in_memory = InMemoryRateLimiter(requests_limit, window_seconds, name)
        self.redis_enabled: bool = True
        self._redis_client = None
        self._redis_available: Optional[bool] = None
        self._last_redis_check: float = 0

    def set_redis_client(self, client):
        """Inject a Redis client (useful for testing distributed rate limiting)."""
        self._redis_client = client
        self._redis_available = True if client is not None else None
        self.redis_enabled = client is not None

    def _get_redis(self):
        if not self.redis_enabled:
            return None

        if self._redis_client is not None and self._redis_available:
            return self._redis_client

        now = time.time()
        # If Redis recently failed, skip retry for 30s to avoid latency
        if self._redis_available is False and (now - self._last_redis_check) < 30:
            return None

        if self._redis_client is None:
            try:
                import redis
                self._redis_client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.2,
                )
            except Exception:
                self._redis_available = False
                self._last_redis_check = now
                return None

        try:
            self._redis_client.ping()
            self._redis_available = True
            return self._redis_client
        except Exception:
            self._redis_available = False
            self._last_redis_check = now
            return None

    def check(self, key: str) -> None:
        r = self._get_redis()
        if r is not None:
            try:
                redis_key = f"ratelimit:{self.name}:{key}"
                now = time.time()
                member = f"{now}:{uuid.uuid4().hex[:8]}"

                # Atomic execution via Lua script
                result = r.eval(
                    SLIDING_WINDOW_LUA,
                    1,
                    redis_key,
                    str(now),
                    str(self.window_seconds),
                    str(self.requests_limit),
                    member,
                )
                allowed = int(result[0])
                if allowed == 0:
                    retry_after = int(result[1])
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded for {self.name.lower()}. Maximum {self.requests_limit} attempts per {self.window_seconds} seconds.",
                        headers={"Retry-After": str(retry_after)},
                    )
                return
            except HTTPException:
                raise
            except Exception:
                # Mark unavailable and fall back to in-memory limiter
                self._redis_available = False
                self._last_redis_check = time.time()

        # In-memory atomic fallback
        self.in_memory.check(key)

    def reset(self) -> None:
        self.in_memory.reset()
        if self.redis_enabled and self._redis_client and self._redis_available:
            try:
                keys = self._redis_client.keys(f"ratelimit:{self.name}:*")
                if keys:
                    self._redis_client.delete(*keys)
            except Exception:
                pass


login_limiter = HybridRateLimiter(requests_limit=5, window_seconds=60, name="Sign-in")
forgot_password_limiter = HybridRateLimiter(requests_limit=5, window_seconds=60, name="Password reset request")
reset_password_limiter = HybridRateLimiter(requests_limit=5, window_seconds=60, name="Password reset")


def _get_client_ip(request: Request) -> str:
    """
    Derives client IP address.
    Strictly ignores X-Forwarded-For unless settings.TRUST_PROXY_HEADERS is explicitly True,
    preventing rate-limit bypass via spoofed request headers.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown_client"


async def rate_limit_login(request: Request) -> None:
    ip = _get_client_ip(request)
    login_limiter.check(ip)


async def rate_limit_forgot_password(request: Request) -> None:
    ip = _get_client_ip(request)
    forgot_password_limiter.check(ip)


async def rate_limit_reset_password(request: Request) -> None:
    ip = _get_client_ip(request)
    reset_password_limiter.check(ip)
