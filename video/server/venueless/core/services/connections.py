import time

from django.conf import settings

from venueless.core.utils.redis import aredis


async def register_connection():
    async with aredis() as redis:
        tr = redis.pipeline(transaction=False)
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
    async with aredis() as redis:
        await redis.hincrby(
            "connections",
            f"{settings.VENUELESS_COMMIT}.{settings.VENUELESS_ENVIRONMENT}",
            -1,
        )


async def register_user_connection(user_id, channel_name):
    async with aredis() as redis:
        tr = redis.pipeline(transaction=False)
        tr.rpush(
            f"connections.list.user:{user_id}",
            channel_name,
        )
        tr.expire(
            f"connections.list.user:{user_id}",
            90,
        )
        await tr.execute()


async def unregister_user_connection(user_id, channel_name):
    async with aredis() as redis:
        await redis.lrem(
            f"connections.list.user:{user_id}",
            0,
            channel_name,
        )


async def get_user_connection_count(user_id):
    async with aredis() as redis:
        print(
            f"connections.list.user:{user_id}",
            await redis.llen(
                f"connections.list.user:{user_id}",
            ),
        )
        return await redis.llen(
            f"connections.list.user:{user_id}",
        )


async def ping_connection(last_ping, user=None):
    n = time.time()
    if n - last_ping < 50:
        return last_ping
    async with aredis() as redis:
        tr = redis.pipeline(transaction=False)
        if user:
            tr.expire(
                f"connections.list.user:{user.id}",
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
    async with aredis() as redis:
        conns = await redis.hgetall("connections")
        ret = {}
        for k, v in conns.items():
            if v == 0 or await redis.get(f"connections:{k.decode()}") != b"exists":
                await redis.hdel("connections", k)
            else:
                ret[k.decode()] = int(v.decode())
        return ret
