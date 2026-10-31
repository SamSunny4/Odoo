import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException, status


class InMemoryRateLimiter:
    """
    In-memory sliding window rate limiter for abuse prevention on auth endpoints.
    Tracks timestamps per client key (IP address) within a configurable window.
    """
    def __init__(self, requests_limit: int = 5, window_seconds: int = 60, name: str = "Request"):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.name = name
        self.history: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> None:
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
        """Clear recorded attempts (useful for tests)."""
        self.history.clear()


login_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60, name="Sign-in")
forgot_password_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60, name="Password reset request")
reset_password_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60, name="Password reset")


def _get_client_ip(request: Request) -> str:
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

