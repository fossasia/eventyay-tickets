import binascii
from contextlib import asynccontextmanager

from channels.layers import get_channel_layer
from django.conf import settings


def consistent_hash(value):
    """
    Maps the value to a node value between 0 and 4095
    using CRC, then down to one of the ring nodes.
    """
    if isinstance(value, str):
        value = value.encode("utf8")
    bigval = binascii.crc32(value) & 0xFFF
    ring_divisor = 4096 / float(len(settings.REDIS_HOSTS))
    return int(bigval / ring_divisor)


if settings.REDIS_USE_PUBSUB:

    @asynccontextmanager
    async def aioredis(shard_key=None):
        if shard_key:
            shard_index = consistent_hash(shard_key)
        else:
            shard_index = 0
        import logging

        logging.getLogger(__name__).warning(
            f"shard key {shard_key} {abs(hash(shard_key))} {shard_index}/{len(settings.REDIS_HOSTS)}"
        )
        conn = await get_channel_layer()._shards[shard_index]._get_pub_conn()
        yield conn


else:

    def aioredis(shard_key=None):
        if shard_key:
            shard_index = consistent_hash(shard_key)
        else:
            shard_index = 0
        return get_channel_layer().connection(shard_index)


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
