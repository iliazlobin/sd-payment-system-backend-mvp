"""Async Redis client and FastAPI dependency."""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from payment.config import settings

redis_client: Redis | None = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency that yields the shared async Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis_client
    finally:
        pass


async def close_redis() -> None:
    """Close the Redis connection pool (called during shutdown)."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
