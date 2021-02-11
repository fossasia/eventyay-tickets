import time

from django.conf import settings

from venueless.core.utils.redis import aioredis


async def register_connection():
    async with aioredis() as redis:
        tr = redis.multi_exec()
        tr.hincrby(
            "connections",
            f"{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            1,
        )
        tr.setex(
            f"connections:{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            60,
            "exists",
        )
        await tr.execute()


async def unregister_connection():
    async with aioredis() as redis:
        await redis.hincrby(
            "connections",
            f"{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            -1,
        )


async def register_user_connection(user_id, socket_id):
    async with aioredis() as redis:
        tr = redis.multi_exec()
        tr.sadd(
            f"connections.user:{user_id}",
            socket_id,
        )
        tr.expire(
            f"connections.user:{user_id}",
            90,
        )
        await tr.execute()


async def unregister_user_connection(user_id, socket_id):
    async with aioredis() as redis:
        await redis.srem(
            f"connections.user:{user_id}",
            socket_id,
        )


async def get_user_connection_count(user_id):
    async with aioredis() as redis:
        return await redis.scard(
            f"connections.user:{user_id}",
        )


async def ping_connection(last_ping, user=None):
    n = time.time()
    if n - last_ping < 50:
        return last_ping
    async with aioredis() as redis:
        tr = redis.multi_exec()
        if user:
            tr.expire(
                f"connections.user:{user.id}",
                90,
            )
        tr.setex(
            f"connections:{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            60,
            "exists",
        )
        await tr.execute()
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
