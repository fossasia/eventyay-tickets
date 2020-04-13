import uuid

from ..utils.redis import get_json, set_json


async def get_user_by_user_id(user_id):
    return await get_json(f"user:{user_id}")


async def get_public_user(user_id):
    data = await get_user_by_user_id(user_id)
    result = {}
    for key in ["user_id", "public_name", "avatar"]:
        value = data.get(key)
        if value:
            result[key] = value
    return result


async def get_user(user_id=None, token=None, client_id=None):
    if user_id:
        return await get_user_by_user_id(user_id)

    uid = None
    if token:
        uid = token["uid"]
        data = await get_json(f"user:by_uid:{uid}")
    elif client_id:
        data = await get_json(f"user:by_client_id:{client_id}")
    else:
        raise Exception("get_user was called without valid user_id, token or client_id")

    if data:
        data = await get_user_by_user_id(data)
        if token and (data.get("traits") != token.get("traits")):
            data["traits"] = token["traits"]
        await update_user(data, data)
        return data

    data = {"user_id": str(uuid.uuid4())}
    if uid:
        data["uid"] = uid
        data["traits"] = token.get("traits")
        await set_json(f"user:by_uid:{uid}", data["user_id"])
    else:
        data["client_id"] = client_id
        await set_json(f"user:by_client_id:{client_id}", data["user_id"])

    await update_user(data, data)
    return data


async def update_user(user, data=None):
    redis_key = f"user:{user['user_id']}"
    stored_data = await get_json(redis_key, {})
    for key, value in data.items():
        stored_data[key] = value
    await set_json(redis_key, stored_data)
    return stored_data
