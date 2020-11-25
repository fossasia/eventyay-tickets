import time

from django.conf import settings

from venueless.core.utils.redis import aioredis


async def register_connection():
    async with aioredis() as redis:
        await redis.hincrby(
            "connections",
            f"{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            1,
        )
        await redis.setex(
            f"connections:{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            60,
            "exists",
        )


async def unregister_connection():
    async with aioredis() as redis:
        await redis.hincrby(
            "connections",
            f"{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            -1,
        )


async def ping_connection(last_ping):
    n = time.time()
    if n - last_ping < 50:
        return last_ping
    async with aioredis() as redis:
        await redis.setex(
            f"connections:{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            60,
            "exists",
        )
    return n


async def get_connections():
    async with aioredis() as redis:
        conns = await redis.hgetall("connections")
        ret = {}
        for k, v in conns.items():
            if v == 0 or await redis.get(f"connections:{k.decode()}") != b"exists":
                await redis.hdel("connections", k)
            else:
                ret[k.decode()] = int(v.decode())
        return ret
