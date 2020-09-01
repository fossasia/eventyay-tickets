import copy
import datetime
import uuid
from contextlib import suppress

import jwt
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from pytz import common_timezones
from rest_framework import serializers

from venueless.core.models import AuditLog, Channel, Room, World
from venueless.core.models.room import RoomConfigSerializer
from venueless.core.permissions import Permission


class WorldConfigSerializer(serializers.Serializer):
    theme = serializers.DictField()
    roles = serializers.DictField()
    trait_grants = serializers.DictField()
    bbb_defaults = serializers.DictField()
    pretalx = serializers.DictField()
    title = serializers.CharField()
    locale = serializers.CharField()
    dateLocale = serializers.CharField()
    videoPlayer = serializers.DictField(allow_null=True)
    timezone = serializers.ChoiceField(choices=[(a, a) for a in common_timezones])
    connection_limit = serializers.IntegerField(allow_null=True)
    available_permissions = serializers.SerializerMethodField("_available_permissions")

    def _available_permissions(self, *args):
        return [d.value for d in Permission]


@database_sync_to_async
def _get_world(world_id):
    return World.objects.filter(id=world_id).first()


async def get_world(world_id):
    world = await _get_world(world_id)
    return world


def get_rooms(world, user):
    qs = world.rooms.filter(deleted=False).prefetch_related("channel")
    if user:
        qs = qs.with_permission(world=world, user=user)
    return list(qs)


@database_sync_to_async
def _get_room(**kwargs):
    return (
        Room.objects.filter(deleted=False)
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
    await get_channel_layer().group_send(
        f"world.{world_id}",
        {
            "type": "world.update",
        },
    )


def get_room_config(room, permissions):
    room_config = {
        "id": str(room.id),
        "name": room.name,
        "description": room.description,
        "picture": room.picture.url if room.picture else None,
        "import_id": room.import_id,
        "pretalx_id": room.pretalx_id,
        "permissions": [p for p in permissions if not p.startswith("world:")],
        "force_join": room.force_join,
        "modules": [],
        "schedule_data": room.schedule_data or None,
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
@transaction.atomic()
def _create_room(data, with_channel=False, permission_preset="public", creator=None):
    if "sorting_priority" not in data:
        data["sorting_priority"] = (
            Room.objects.filter(world=data["world"]).aggregate(
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

    if (
        data.get("world")
        .rooms.filter(deleted=False, name__iexact=data.get("name"))
        .exists()
    ):
        raise ValidationError("This room name is already taken.", code="name_taken")
    room = Room.objects.create(**data)
    if creator:
        room.role_grants.create(world=room.world, user=creator, role="room_owner")
    channel = None
    if with_channel:
        channel = Channel.objects.create(world_id=room.world_id, room=room)

    AuditLog.objects.create(
        world_id=room.world_id,
        user=creator,
        type="world.room.added",
        data={
            "object": str(room.id),
            "new": RoomConfigSerializer(room).data,
        },
    )
    return room, channel


async def create_room(world, data, creator):
    types = {m["type"] for m in data.get("modules", [])}
    if "chat.native" in types:
        if not await world.has_permission_async(
            user=creator, permission=Permission.WORLD_ROOMS_CREATE_CHAT
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.", code="denied"
            )
        m = [m for m in data.get("modules", []) if m["type"] == "chat.native"][0]
        m["config"] = {"volatile": m.get("config", {}).get("volatile", False)}
    elif types == {"call.bigbluebutton"}:
        if not await world.has_permission_async(
            user=creator, permission=Permission.WORLD_ROOMS_CREATE_BBB
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.", code="denied"
            )
        m = [m for m in data.get("modules", []) if m["type"] == "call.bigbluebutton"][0]
        m["config"] = {}
    elif "livestream.native" in types:
        if not await world.has_permission_async(
            user=creator, permission=Permission.WORLD_ROOMS_CREATE_STAGE
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.", code="denied"
            )
        m = [m for m in data.get("modules", []) if m["type"] == "livestream.native"][0]
        m["config"] = {"hls_url": m.get("config", {}).get("hls_url", "")}
    else:
        raise ValidationError(
            f"The dynamic creation of rooms with the modules {types} is cuarrently not allowed.",
            code="invalid",
        )

    # TODO input validation
    room, channel = await _create_room(
        {
            "world": world,
            "name": data["name"],
            "description": data["description"],
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


@database_sync_to_async
def generate_tokens(world, number, traits, days, by_user):
    jwt_config = world.config["JWT_secrets"][0]
    secret = jwt_config["secret"]
    audience = jwt_config["audience"]
    issuer = jwt_config["issuer"]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=days)
    result = []
    for i in range(number):
        payload = {
            "iss": issuer,
            "aud": audience,
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": traits,
        }
        token = jwt.encode(payload, secret, algorithm="HS256").decode("utf-8")
        result.append(token)

    AuditLog.objects.create(
        world_id=world.id,
        user=by_user,
        type="world.tokens.generate",
        data={
            "number": number,
            "days": days,
            "traits": traits,
        },
    )
    return result


def _config_serializer(world, *args, **kwargs):
    bbb_defaults = world.config.get("bbb_defaults", {})
    bbb_defaults.pop("secret", None)  # Protect secret legacy contents
    return WorldConfigSerializer(
        instance={
            "theme": world.config.get("theme", {}),
            "title": world.title,
            "locale": world.locale,
            "dateLocale": world.config.get("dateLocale", "en-ie"),
            "roles": world.roles,
            "bbb_defaults": bbb_defaults,
            "pretalx": world.config.get("pretalx", {}),
            "videoPlayer": world.config.get("videoPlayer"),
            "timezone": world.timezone,
            "trait_grants": world.trait_grants,
            "connection_limit": world.config.get("connection_limit", 0),
        },
        *args,
        **kwargs,
    )


@database_sync_to_async
@transaction.atomic
def save_world(world, update_fields, old_data, by_user):
    world.save(update_fields=update_fields)
    new = _config_serializer(world).data

    AuditLog.objects.create(
        world_id=world.id,
        user=by_user,
        type="world.room.updated",
        data={
            "old": old_data,
            "new": new,
        },
    )
    return new
