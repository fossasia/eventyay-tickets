from contextlib import suppress

from ..utils.redis import get_json, set_json


async def get_channel_uids(channel):
    return await get_json(f"channel:{channel}:users", default=[])


async def set_channel_uids(channel, uids):
    return await set_json(f"channel:{channel}:users", uids)


async def get_channel_users(channel):
    from .user import get_public_user

    uids = await get_channel_uids(channel)
    users = [await get_public_user(user_id=uid) for uid in uids]
    return users


async def add_channel_user(channel, uid):
    uids = await get_channel_uids(channel)
    uids = set(uids)
    uids.add(uid)
    return await set_channel_uids(channel, list(uids))


async def remove_channel_user(channel, uid):
    uids = await get_channel_uids(channel)
    uids = set(uids)
    with suppress(KeyError):
        uids.remove(uid)
    return await set_channel_uids(channel, list(uids))
