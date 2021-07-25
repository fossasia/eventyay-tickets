from contextlib import asynccontextmanager

from channels.layers import get_channel_layer
from django.conf import settings

if settings.REDIS_USE_PUBSUB:

    @asynccontextmanager
    async def aioredis():
        conn = await get_channel_layer()._shards[0]._get_pub_conn()
        yield conn


else:

    def aioredis():
        return get_channel_layer().connection(0)


"""
Currently not needed and therefore not covered by tests

async def get_json(key, default=None):
    async with aioredis() as redis:
        data = await redis.get(key)
    result = None
    try:
        result = json.loads(data)
    except (json.decoder.JSONDecodeError, TypeError):
        pass
    if result is None:
        return default
    return result


async def set_json(key, value):
    async with aioredis() as redis:
        await redis.set(key, json.dumps(value))
"""
