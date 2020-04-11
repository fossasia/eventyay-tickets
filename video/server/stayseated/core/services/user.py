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
        await redis.set(key, json.dumps(value))


async def get_user(token=None, client_id=None):
    if token:
        user_id = token["uid"]
        data = await get_json(f"user:user_id:{user_id}", {"user_id": user_id})
        if data.get("traits") != token["traits"]:
            data["traits"] = token["traits"]
    elif client_id:
        data = await get_json(f"user:client_id:{client_id}", {"client_id": client_id})
    else:
        raise Exception("get_user was called without token or client_id")
    await update_user(data, data)
    return data


async def update_user(user, data=None):
    if user.get("user_id"):
        redis_key = f"user:user_id:{user['user_id']}"
    elif user.get("client_id"):
        redis_key = f"user:client_id:{user['client_id']}"
    else:
        raise Exception("Received user without user ID or client ID.")
    stored_data = await get_json(redis_key, {})
    for key, value in data.items():
        stored_data[key] = value
    await set_json(redis_key, stored_data)
