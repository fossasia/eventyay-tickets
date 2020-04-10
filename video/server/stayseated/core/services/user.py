import json

from ..utils.redis import aioredis


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
        redis.set(key, json.dumps(value))


async def get_user(token):
    data = await get_json("user:4", {})
    data["id"] = 4
    return data


async def update_user(user_id, data):
    stored_data = await get_json("user:4", {})
    for key, value in data.items():
        stored_data[key] = value
    await set_json("user:4", stored_data)
