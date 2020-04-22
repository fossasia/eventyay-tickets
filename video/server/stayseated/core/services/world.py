import json
import os

from aiofile import AIOFile

from ...settings import BASE_DIR


async def get_world_config(world_id):
    try:
        async with AIOFile(
            os.path.join(BASE_DIR, "sample", "worlds", world_id + ".json"),
            "r",
            encoding="utf-8",
        ) as afp:
            data = json.loads(await afp.read())
    except OSError:
        return None

    return data


async def get_world_config_for_user(world_id, user):
    world = await get_world_config(world_id)

    # TODO: Check if user has access to this world
    # TODO: Remove any rooms the user should not see

    world["world"].pop("JWT_secrets", None)
    for r in world["rooms"]:
        for m in r["modules"]:
            if m["type"] == "call.bigbluebutton":
                m["config"] = {}
    return world


async def get_room_config(world_id, room_id):
    world = await get_world_config(world_id)
    for r in world["rooms"]:
        if r["id"] == room_id:
            return r
