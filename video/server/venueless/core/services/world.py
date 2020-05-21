import copy
from contextlib import suppress

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db.models import Max

from venueless.core.models import Channel, Room, World


@database_sync_to_async
def _get_world(world_id):
    return World.objects.filter(id=world_id).first()


async def get_world(world_id):
    world = await _get_world(world_id)
    return world


def get_rooms(world, user):
    qs = world.rooms.all().prefetch_related("channel")
    if user:
        qs = qs.with_permission(world=world, user=user)
    return list(qs)


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


def get_permissions_for_traits(rules, traits, prefixes):
    return [
        permission
        for permission, required_traits in rules.items()
        if any(permission.startswith(prefix) for prefix in prefixes)
        and all(trait in traits for trait in required_traits)
    ]


async def notify_world_change(world_id):
    await get_channel_layer().group_send(f"world.{world_id}", {"type": "world.update",})


def get_room_config(room, permissions):
    room_config = {
        "id": str(room.id),
        "name": room.name,
        "picture": room.picture.url if room.picture else None,
        "import_id": room.import_id,
        "permissions": [p for p in permissions if not p.startswith("world:")],
        "modules": [],
    }
    for module in room.module_config:
        module_config = copy.deepcopy(module)
        if module["type"] == "call.bigbluebutton":
            module_config["config"] = {}
        elif module["type"] == "chat.native" and getattr(room, "channel", None):
            module_config["channel_id"] = str(room.channel.id)
        room_config["modules"].append(module_config)
    return room_config


def get_world_config_for_user(world, user):
    permissions = world.get_all_permissions(user)
    result = {
        "world": {
            "id": str(world.id),
            "title": world.title,
            "about": world.about,
            "pretalx": world.config.get("pretalx", {}),
        },
        "permissions": list(permissions[world]),
        "rooms": [],
    }

    rooms = get_rooms(world, user)
    for room in rooms:
        result["rooms"].append(
            get_room_config(room, permissions[world] | permissions[room])
        )
    return result


@database_sync_to_async
def _create_room(data, with_channel=False, permission_preset="public", creator=None):
    if "sorting_priority" not in data:
        data["sorting_priority"] = (
            Room.objects.filter(world_id=data["world_id"]).aggregate(
                m=Max("sorting_priority")
            )["m"]
            or 0
        ) + 1
    if permission_preset == "public":
        data["trait_grants"] = {
            "viewer": [],
            "participant": [],
        }
    else:
        data["trait_grants"] = {}

    room = Room.objects.create(**data)
    if creator:
        room.role_grants.create(world=room.world, user=creator, role="room_owner")
    channel = None
    if with_channel:
        channel = Channel.objects.create(world_id=room.world_id, room=room)
    return room, channel


async def create_room(world, data, creator):
    for m in data.get("modules", []):
        if m.get("type") != "chat.native":
            raise ValidationError(
                f"The dynamic creation of rooms with the module '"
                f"{m['type']}' is currently not allowed."
            )

    # TODO input validation
    room, channel = await _create_room(
        {
            "world_id": world.id,
            "name": data["name"],
            "module_config": data.get("modules", []),
        },
        permission_preset=data.get("permission_preset", "public"),
        creator=creator,
        with_channel=any(
            d.get("type") == "chat.native" for d in data.get("modules", [])
        ),
    )
    await get_channel_layer().group_send(
        f"world.{world.id}", {"type": "room.create", "room": str(room.id)}
    )
    return {"room": str(room.id), "channel": str(channel.id) if channel else None}


async def get_room_config_for_user(room: str, world_id: str, user):
    room = await get_room(id=room, world_id=world_id)
    permissions = await database_sync_to_async(room.world.get_all_permissions)(user)
    return get_room_config(room, permissions[room] | permissions[room.world])
