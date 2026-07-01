from fastapi import Depends, HTTPException, Request

from app.core.redis import sliding_window_rate_limit


def rate_limit(limit: int, window_seconds: int, key_prefix: str = "rl"):
    """FastAPI dependency factory for rate limiting."""

    async def _rate_limit(request: Request):
        # Use IP address as the key by default
        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}"

        allowed, retry_after = await sliding_window_rate_limit(key, limit, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests, please try again later",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

    return Depends(_rate_limit)


def rate_limit_by_user(limit: int, window_seconds: int, key_prefix: str = "rl_user"):
    """Rate limit keyed by authenticated user ID."""

    async def _rate_limit(request: Request):
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            client_ip = request.client.host if request.client else "unknown"
            key = f"{key_prefix}:ip:{client_ip}"
        else:
            key = f"{key_prefix}:{user_id}"

        allowed, retry_after = await sliding_window_rate_limit(key, limit, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests, please try again later",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

    return Depends(_rate_limit)
