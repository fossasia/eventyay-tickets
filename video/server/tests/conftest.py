import pytest


@pytest.fixture(autouse=True)
async def clear_redis():
    from stayseated.core.utils.redis import aioredis

    async with aioredis() as redis:
        redis.flushall()
