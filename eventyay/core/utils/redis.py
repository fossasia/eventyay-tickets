import binascii
import os
from contextlib import asynccontextmanager

import redis
from channels.layers import get_channel_layer
from channels_redis.utils import create_pool
from django.conf import settings
from redis import asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff


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
    _pool = {}

    @asynccontextmanager
    async def aredis(shard_key=None):
        global _pool

        if shard_key:
            shard_index = consistent_hash(shard_key)
        else:
            shard_index = 0

        if "PYTEST_CURRENT_TEST" in os.environ:
            # During tests, async is... different.
            shard = get_channel_layer()._shards[shard_index]
            async with shard._lock:
                shard._ensure_redis()
            yield shard._redis
            return

        if shard_index not in _pool:
            shard = get_channel_layer()._shards[shard_index]
            _pool[shard_index] = create_pool(shard.host)

        def _make_conn():
            return aioredis.Redis(
                connection_pool=_pool[shard_index],
                retry=Retry(ExponentialBackoff(), 3),
                retry_on_error=[redis.exceptions.ConnectionError],
                retry_on_timeout=True,
            )

        try:
            conn = _make_conn()
            await conn.ping()
        except redis.exceptions.ConnectionError:  # retry once
            conn = _make_conn()
            await conn.ping()

        try:
            yield conn
        finally:
            await conn.aclose()

else:

    def aredis(shard_key=None):
        if shard_key:
            shard_index = consistent_hash(shard_key)
        else:
            shard_index = 0
        return get_channel_layer().connection(shard_index)


async def flush_aredis_pool():
    global _pool

    if settings.REDIS_USE_PUBSUB:
        for v in _pool.values():
            await v.aclose()
        _pool.clear()


"""
Currently not needed and therefore not covered by tests

async def get_json(key, default=None):
    async with aredis() as redis:
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
    async with aredis() as redis:
        await redis.set(key, json.dumps(value))
"""
