import copy
from contextlib import suppress

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError

from venueless.core.models import Channel, Room, World


@database_sync_to_async
def _get_world(world_id):
    return World.objects.filter(id=world_id).first()


async def get_world(world_id):
    world = await _get_world(world_id)
    return world


@database_sync_to_async
def _get_rooms(world):
    return list(world.rooms.all().prefetch_related("channel"))


async def get_rooms(world):
    rooms = await _get_rooms(world)
    return rooms


@database_sync_to_async
def _get_room(**kwargs):
    return (
        Room.objects.all()
        .prefetch_related("channel")
        .select_related("world")
        .get(**kwargs)
    )


async def get_room(**kwargs):
    with suppress(Room.DoesNotExist, Room.MultipleObjectsReturned, ValidationError):
        room = await _get_room(**kwargs)
        return room


@database_sync_to_async
def get_world_for_user(user):
    return user.world


def get_permissions_for_traits(rules, traits, prefixes):
    return [
        permission
        for permission, required_traits in rules.items()
        if any(permission.startswith(prefix) for prefix in prefixes)
        and all(trait in traits for trait in required_traits)
    ]


async def notify_world_change(world_id):
    await get_channel_layer().group_send(f"world.{world_id}", {"type": "world.update",})


def get_room_config(room, world, traits):
    rules = world.permission_config or {}
    room_rules = {**rules, **(room.permission_config or {})}
    room_config = {
        "id": str(room.id),
        "name": room.name,
        "picture": room.picture.url if room.picture else None,
        "import_id": room.import_id,
        "permissions": get_permissions_for_traits(
            room_rules, traits, prefixes=["room"]
        ),
        "modules": [],
    }
    for module in room.module_config:
        module_config = copy.deepcopy(module)
        module_config["permissions"] = get_permissions_for_traits(
            {**room_rules, **module_config.pop("permissions", {})},
            traits,
            prefixes=[module["type"], module["type"].split(".")[0]],
        )
        if module["type"] == "call.bigbluebutton":
            module_config["config"] = {}
        elif module["type"] == "chat.native" and getattr(room, "channel", None):
            module_config["channel_id"] = str(room.channel.id)
        room_config["modules"].append(module_config)
    return room_config


async def get_world_config_for_user(user):
    # TODO: Remove any rooms the user should not see
    world = await get_world_for_user(user)
    result = {
        "world": {
            "id": str(world.id),
            "title": world.title,
            "about": world.about,
            "pretalx": world.config.get("pretalx", {}),
        },
        "rooms": [],
    }

    traits = set(user.traits)
    rules = world.permission_config or {}
    result["permissions"] = get_permissions_for_traits(
        rules, traits, prefixes=["world", "room.create"]
    )
    rooms = await get_rooms(world)
    for room in rooms:
        result["rooms"].append(get_room_config(room, world, traits))
    return result


@database_sync_to_async
def _create_room(data, with_channel=False):
    room = Room.objects.create(**data)
    channel = None
    if with_channel:
        channel = Channel.objects.create(world_id=room.world_id, room=room)
    return room, channel


async def create_room(world, data):
    # TODO input validation
    room, channel = await _create_room(
        {
            "world_id": world.id,
            "name": data["name"],
            "module_config": data.get("modules", []),
            # TODO sorting_priority
        },
        with_channel=any(
            d.get("type") == "chat.native" for d in data.get("modules", [])
        ),
    )
    await get_channel_layer().group_send(
        f"world.{world.id}", {"type": "room.create", "room": str(room.id)}
    )
    return {"room": str(room.id), "channel": str(channel.id) if channel else None}


async def get_room_config_for_user(room: str, world: str, user):
    room = await get_room(id=room, world_id=world)
    return get_room_config(room, room.world, traits=set(user.traits))
