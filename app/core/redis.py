import time
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def sliding_window_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Sliding window rate limiter.
    Returns (allowed: bool, retry_after_seconds: int).
    """
    redis = get_redis()
    now = time.time()
    window_start = now - window_seconds

    await redis.zremrangebyscore(key, "-inf", window_start)
    await redis.zadd(key, {str(now): now})
    current_count = await redis.zcard(key)
    await redis.expire(key, window_seconds)

    if current_count > limit:
        oldest = await redis.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_time = oldest[0][1]
            retry_after = int(oldest_time + window_seconds - now) + 1
        else:
            retry_after = window_seconds
        return False, retry_after

    return True, 0


async def store_refresh_token(user_id: str, jti: str, ttl_seconds: int) -> None:
    redis = get_redis()
    key = f"refresh_token:{user_id}:{jti}"
    await redis.setex(key, ttl_seconds, "valid")


async def invalidate_refresh_token(user_id: str, jti: str) -> None:
    redis = get_redis()
    key = f"refresh_token:{user_id}:{jti}"
    await redis.delete(key)


async def is_refresh_token_valid(user_id: str, jti: str) -> bool:
    redis = get_redis()
    key = f"refresh_token:{user_id}:{jti}"
    value = await redis.get(key)
    return value == "valid"


async def update_session_activity(session_id: str) -> None:
    redis = get_redis()
    key = f"session_activity:{session_id}"
    await redis.set(key, str(time.time()), ex=7200)  # 2-hour max


async def get_session_last_activity(session_id: str) -> Optional[float]:
    redis = get_redis()
    key = f"session_activity:{session_id}"
    value = await redis.get(key)
    return float(value) if value else None


async def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    redis = get_redis()
    await redis.setex(key, ttl_seconds, value)


async def cache_get(key: str) -> Optional[str]:
    redis = get_redis()
    return await redis.get(key)


async def cache_delete(key: str) -> None:
    redis = get_redis()
    await redis.delete(key)
