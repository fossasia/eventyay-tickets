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


def get_permissions_for_traits(rules, traits, prefixes):
    return [
        permission
        for permission, required_traits in rules.items()
        if any(permission.startswith(prefix) for prefix in prefixes)
        and all(trait in traits for trait in required_traits)
    ]


async def get_world_config_for_user(world_id, user):
    world = await get_world_config(world_id)

    # TODO: Check if user has access to this world
    # TODO: Remove any rooms the user should not see

    world["world"].pop("JWT_secrets", None)
    rules = world.pop("permissions", {})
    traits = set(user.traits)
    world["permissions"] = get_permissions_for_traits(rules, traits, prefixes=["world"])
    for room in world["rooms"]:
        room_rules = {**rules, **room.pop("permissions", {})}
        room["permissions"] = get_permissions_for_traits(
            room_rules, traits, prefixes=["room"]
        )
        for module in room["modules"]:
            module["permissions"] = get_permissions_for_traits(
                {**room_rules, **module.pop("permissions", {})},
                traits,
                prefixes=[module["type"], module["type"].split(".")[0]],
            )
            if module["type"] == "call.bigbluebutton":
                module["config"] = {}
    return world


async def get_room_config(world_id, room_id):
    world = await get_world_config(world_id)
    for r in world["rooms"]:
        if r["id"] == room_id:
            return r
