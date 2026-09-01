import logging
from typing import Callable
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.redis_service import redis_service

logger = logging.getLogger("sutra.ratelimit")

# Standard slowapi limiter backed by Redis or remote IP
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    enabled=settings.rate_limit_enabled,
)


def enforce_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    action_name: str = "request",
    fail_closed: bool = True,
):
    """
    Enforce an atomic Redis rate limit.
    If limit is exceeded, raises HTTP 429 Too Many Requests.
    If Redis is down:
      - If fail_closed is True: raises HTTP 503 / 429 for security.
      - If fail_closed is False: logs error and permits request.
    """
    if not settings.rate_limit_enabled:
        return

    full_key = f"ratelimit:{key}"
    try:
        allowed, current, ttl = redis_service.check_rate_limit(
            full_key,
            max_requests,
            window_seconds,
        )
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {key} on {action_name}: {current}/{max_requests} in {window_seconds}s. TTL: {ttl}s"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many {action_name}s. Please wait {ttl} seconds before trying again.",
                headers={"Retry-After": str(ttl)},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Redis rate limit check failed for {key}: {e}")
        if fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security service temporarily unavailable. Please try again shortly.",
            )


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
