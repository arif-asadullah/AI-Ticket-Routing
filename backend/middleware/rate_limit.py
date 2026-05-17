"""Redis sliding-window rate limiter middleware.

Per-user:  50 requests/minute (on ticket creation)
Global:   200 requests/minute (on ticket creation)

Returns 429 with Retry-After header when exceeded.
Adds X-RateLimit-Remaining header to all ticket responses.
"""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

USER_LIMIT = 50       # per user per window
GLOBAL_LIMIT = 200    # global per window
WINDOW_SECONDS = 60   # 1 minute sliding window

# Only rate-limit ticket creation (the expensive operation)
RATE_LIMITED_PATHS = {"/api/tickets"}
RATE_LIMITED_METHODS = {"POST"}


def _extract_user_email(request: Request) -> str | None:
    """Extract user email from JWT without full DB lookup."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        from backend.core.auth import decode_token
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except Exception:
        return None


async def _sliding_window_count(redis_client, key: str, window: int) -> int:
    """Increment and return count using Redis sorted set sliding window."""
    now = time.time()
    window_start = now - window

    pipe = redis_client.pipeline()
    # Remove expired entries
    pipe.zremrangebyscore(key, 0, window_start)
    # Add current request
    pipe.zadd(key, {str(now): now})
    # Count entries in window
    pipe.zcard(key)
    # Set expiry on the key itself (cleanup)
    pipe.expire(key, window + 1)
    results = await pipe.execute()

    return results[2]  # zcard result


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only rate-limit specific paths/methods
        if request.url.path not in RATE_LIMITED_PATHS or request.method not in RATE_LIMITED_METHODS:
            return await call_next(request)

        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is None:
            # No Redis → skip rate limiting (graceful degradation)
            return await call_next(request)

        email = _extract_user_email(request)
        remaining_user = USER_LIMIT
        remaining_global = GLOBAL_LIMIT

        try:
            # Check global limit
            global_count = await _sliding_window_count(
                redis_client, "ratelimit:global", WINDOW_SECONDS
            )
            remaining_global = max(GLOBAL_LIMIT - global_count, 0)

            if global_count > GLOBAL_LIMIT:
                logger.warning("Rate limit exceeded: global (%d/%d)", global_count, GLOBAL_LIMIT)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Global rate limit exceeded. Try again later."},
                    headers={
                        "Retry-After": str(WINDOW_SECONDS),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Limit": str(GLOBAL_LIMIT),
                    },
                )

            # Check per-user limit
            if email:
                user_count = await _sliding_window_count(
                    redis_client, f"ratelimit:user:{email}", WINDOW_SECONDS
                )
                remaining_user = max(USER_LIMIT - user_count, 0)

                if user_count > USER_LIMIT:
                    logger.warning("Rate limit exceeded: user %s (%d/%d)", email, user_count, USER_LIMIT)
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded. Try again later."},
                        headers={
                            "Retry-After": str(WINDOW_SECONDS),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Limit": str(USER_LIMIT),
                        },
                    )
        except Exception as exc:
            # Redis error → skip rate limiting
            logger.warning("Rate limit check failed: %s", exc)
            return await call_next(request)

        # Proceed with request
        response: Response = await call_next(request)

        # Add rate limit headers
        remaining = min(remaining_user, remaining_global)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(USER_LIMIT)

        return response
