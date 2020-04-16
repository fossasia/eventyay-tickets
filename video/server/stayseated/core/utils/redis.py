from channels.layers import get_channel_layer


def aioredis():
    # TODO: we're assuming there is no sharding
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
