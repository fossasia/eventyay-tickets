import copy
import datetime
import uuid
from contextlib import suppress

import jwt
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, OuterRef, Subquery, Q
from pytz import common_timezones
from rest_framework import serializers

from eventyay.base.models.room import Room
from eventyay.base.models.event import Event
from eventyay.base.models.room import RoomConfigSerializer, RoomView
from eventyay.core.permissions import Permission
# Add missing imports for models referenced in this module
from eventyay.base.models.chat import Channel
from eventyay.base.models.audit import AuditLog


class EventConfigSerializer(serializers.Serializer):
    theme = serializers.DictField()
    roles = serializers.DictField()
    trait_grants = serializers.DictField()
    bbb_defaults = serializers.DictField()
    pretalx = serializers.DictField()
    title = serializers.CharField()
    locale = serializers.CharField()
    date_locale = serializers.CharField()
    video_player = serializers.DictField(allow_null=True)
    timezone = serializers.ChoiceField(choices=[(a, a) for a in common_timezones])
    connection_limit = serializers.IntegerField(allow_null=True)
    available_permissions = serializers.SerializerMethodField("_available_permissions")
    profile_fields = serializers.JSONField()
    social_logins = serializers.ListSerializer(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    iframe_blockers = serializers.JSONField()
    track_exhibitor_views = serializers.BooleanField()
    track_room_views = serializers.BooleanField()
    track_event_views = serializers.BooleanField()
    onsite_traits = serializers.JSONField(
        required=False,
        allow_null=False,
    )
    conftool_url = serializers.URLField(
        required=False, allow_null=True, allow_blank=True
    )
    conftool_password = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    def _available_permissions(self, *args):
        return [d.value for d in Permission]

    def validate_social_logins(self, val):
        known = ("gravatar", "twitter", "linkedin")
        if any(v not in known for v in val):
            raise ValidationError("Invalid value for social_logins")

        if "twitter" in val and not settings.TWITTER_CLIENT_ID:
            raise ValidationError(
                "Twitter login can't be enabled since there's no Twitter API keys set for this "
                "Eventyay installation."
            )

        if "linkedin" in val and not settings.LINKEDIN_CLIENT_ID:
            raise ValidationError(
                "LinkedIn login can't be enabled since there's no LinkedIn API keys set for this "
                "Eventyay installation."
            )

        return val


@database_sync_to_async
def _get_event(event_id):
    """Retrieve Event by primary key or slug.
    Frontend passes <event_identifier> in /video/<event_identifier>/ and websocket /ws/event/<event_identifier>/.
    Previously only numeric primary key worked; now also accept slug.
    """
    # Try numeric ID first if it looks like one
    if isinstance(event_id, str) and event_id.isdigit():
        evt = Event.objects.filter(id=int(event_id)).first()
        if evt:
            return evt
    # Fallback: match by slug OR (string) id (covers atypical string PK setups)
    return Event.objects.filter(Q(slug=event_id) | Q(id=event_id)).first()


async def get_event(event_id):
    event = await _get_event(event_id)
    return event


def get_rooms(event, user):
    qs = (
        event.rooms.filter(deleted=False)
        .prefetch_related("channel")
        .annotate(
            current_roomviews=Subquery(
                RoomView.objects.filter(room_id=OuterRef("pk"), end__isnull=True)
                .values("room_id")
                .order_by()
                .annotate(
                    # Count('user_id', distinct=True) would be more accurate, but might be slow, and we don't need accurate
                    c=Count("user_id")
                )
                .values("c")
            )
        )
    )
    if user:
        qs = qs.with_permission(event=event, user=user)
    return list(qs)


@database_sync_to_async
def _get_room(**kwargs):
    return (
        Room.objects.filter(deleted=False)
        .prefetch_related("channel")
        .select_related("event")
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


async def notify_event_change(event_id):
    await get_channel_layer().group_send(
        f"event.{event_id}",
        {
            "type": "event.update",
        },
    )


async def notify_schedule_change(event_id):
    await get_channel_layer().group_send(
        f"event.{event_id}",
        {
            "type": "event.schedule.update",
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
        "permissions": [p for p in permissions if not p.startswith("event:")],
        "force_join": room.force_join,
        "modules": [],
        "schedule_data": room.schedule_data or None,
    }

    if hasattr(room, "current_roomviews"):
        # set actual viewer count instead of approximate text
        room_config["users"] = room.current_roomviews

    for module in room.module_config:
        module_config = copy.deepcopy(module)
        if module["type"] == "call.bigbluebutton":
            module_config["config"] = {}
        elif module["type"] == "chat.native" and getattr(room, "channel", None):
            module_config["channel_id"] = str(room.channel.id)
        room_config["modules"].append(module_config)
    return room_config


def get_event_config_for_user(event, user):
    permissions = event.get_all_permissions(user)
    cfg = event.config or {}
    world_block = {
        "id": str(event.id),
        "title": getattr(event, "title", getattr(event, "name", "")),
        "pretalx": cfg.get("pretalx", {}),
        "profile_fields": cfg.get("profile_fields", []),
        "social_logins": cfg.get("social_logins", []),
        "iframe_blockers": cfg.get(
            "iframe_blockers",
            {"default": {"enabled": False, "policy_url": None}},
        ),
        "onsite_traits": cfg.get("onsite_traits", []),
    }
    # Build permission strings and include world:* aliases for event:* permissions for frontend compatibility
    event_perm_values = [
        p if isinstance(p, str) else p.value for p in permissions[event]
    ]
    world_aliases = []
    for p in event_perm_values:
        if p == "event.view":
            world_aliases.append("world:view")
        elif p.startswith("event:"):
            world_aliases.append("world:" + p[len("event:"):])
    merged_permissions = sorted(set(event_perm_values) | set(world_aliases))

    result = {
        # Provide both keys for compatibility: frontend expects 'world', prior code used 'event'
        "world": world_block,
        "event": world_block,
        "permissions": merged_permissions,
        "rooms": [],
    }

    rooms = get_rooms(event, user)
    for room in rooms:
        result["rooms"].append(
            get_room_config(room, permissions[event] | permissions[room])
        )
    return result


@database_sync_to_async
@transaction.atomic()
def _create_room(data, with_channel=False, permission_preset="public", creator=None):
    if "sorting_priority" not in data:
        data["sorting_priority"] = (
            Room.objects.filter(event=data["event"]).aggregate(
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
        data.get("event")
        .rooms.filter(deleted=False, name__iexact=data.get("name"))
        .exists()
    ):
        raise ValidationError("This room name is already taken.", code="name_taken")
    room = Room.objects.create(**data)
    if creator:
        room.role_grants.create(event=room.event, user=creator, role="room_owner")
    channel = None
    if with_channel:
        channel = Channel.objects.create(event_id=room.event_id, room=room)

    AuditLog.objects.create(
        event_id=room.event_id,
        user=creator,
        type="event.room.added",
        data={
            "object": str(room.id),
            "new": RoomConfigSerializer(room).data,
        },
    )
    return room, channel


async def create_room(event, data, creator):
    types = {m["type"] for m in data.get("modules", [])}
    if "chat.native" in types:
        if not await event.has_permission_async(
            user=creator, permission=Permission.EVENT_ROOMS_CREATE_CHAT
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )
        m = [m for m in data.get("modules", []) if m["type"] == "chat.native"][0]
        m["config"] = {"volatile": m.get("config", {}).get("volatile", False)}
    elif types == {"call.bigbluebutton"}:
        if not await event.has_permission_async(
            user=creator, permission=Permission.EVENT_ROOMS_CREATE_BBB
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )
        m = [m for m in data.get("modules", []) if m["type"] == "call.bigbluebutton"][0]
        m["config"] = event.config.get("bbb_defaults", {})
        m["config"].pop("secret", None)  # legacy
    elif "livestream.native" in types:
        if not await event.has_permission_async(
            user=creator, permission=Permission.EVENT_ROOMS_CREATE_STAGE
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )
        m = [m for m in data.get("modules", []) if m["type"] == "livestream.native"][0]
        m["config"] = {"hls_url": m.get("config", {}).get("hls_url", "")}
    elif types == set():
        if not await event.has_permission_async(
            user=creator, permission=Permission.ROOM_UPDATE
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )
    else:
        raise ValidationError(
            f"The dynamic creation of rooms with the modules {types} is currently not allowed.",
            code="invalid",
        )

    # TODO input validation
    room, channel = await _create_room(
        {
            "event": event,
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
        f"event.{event.id}", {"type": "room.create", "room": str(room.id)}
    )

    return {
        "room": str(room.id),
        "channel": str(channel.id) if channel else None,
    }


async def get_room_config_for_user(room: str, event_id: str, user):
    room = await get_room(id=room, event_id=event_id)
    permissions = await database_sync_to_async(room.event.get_all_permissions)(user)
    return get_room_config(room, permissions[room] | permissions[room.event])


@database_sync_to_async
def generate_tokens(event, number, traits, days, by_user, long=False):
    from eventyay.base.models.auth import ShortToken
    jwt_config = event.config["JWT_secrets"][0]
    secret = jwt_config["secret"]
    audience = jwt_config["audience"]
    issuer = jwt_config["issuer"]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=days)
    result = []
    bulk_create = []
    for _ in range(number):
        payload = {
            "iss": issuer,
            "aud": audience,
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": traits,
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        if long:
            result.append(token)
        else:
            st = ShortToken(event=event, long_token=token, expires=exp)
            result.append(st.short_token)
            bulk_create.append(st)

    if not long:
        ShortToken.objects.bulk_create(bulk_create)

    AuditLog.objects.create(
        event_id=event.id,
        user=by_user,
        type="event.tokens.generate",
        data={
            "number": number,
            "days": days,
            "traits": traits,
            "long": long,
        },
    )
    return result


def _config_serializer(event, *args, **kwargs):
    bbb_defaults = (event.config or {}).get("bbb_defaults", {})
    bbb_defaults.pop("secret", None)  # Protect secret legacy contents
    cfg = event.config or {}
    return EventConfigSerializer(
        instance={
            "theme": cfg.get("theme", {}),
            "title": getattr(event, "title", getattr(event, "name", "")),
            "locale": event.locale,
            "date_locale": cfg.get("date_locale", "en-ie"),
            "roles": event.roles,
            "bbb_defaults": bbb_defaults,
            "track_exhibitor_views": cfg.get("track_exhibitor_views", True),
            "track_room_views": cfg.get("track_room_views", True),
            "track_event_views": cfg.get("track_event_views", False),
            "pretalx": cfg.get("pretalx", {}),
            "video_player": cfg.get("video_player"),
            "timezone": event.timezone,
            "trait_grants": event.trait_grants,
            "connection_limit": cfg.get("connection_limit", 0),
            "profile_fields": cfg.get("profile_fields", []),
            "social_logins": cfg.get("social_logins", []),
            "onsite_traits": cfg.get("onsite_traits", []),
            "conftool_url": cfg.get("conftool_url", ""),
            "conftool_password": cfg.get("conftool_password", ""),
            "iframe_blockers": cfg.get(
                "iframe_blockers",
                {"default": {"enabled": False, "policy_url": None}},
            ),
        },
        *args,
        **kwargs,
    )


@database_sync_to_async
@transaction.atomic
def save_event(event, update_fields, old_data, by_user):
    event.save(update_fields=update_fields)
    new = _config_serializer(event).data

    AuditLog.objects.create(
        event_id=event.id,
        user=by_user,
        type="event.updated",
        data={
            "old": old_data,
            "new": new,
        },
    )
    return new


@database_sync_to_async
def get_audit_log(event):
    return [
        a.serialize_public()
        for a in AuditLog.objects.filter(
            event_id=event.id,
        ).prefetch_related("user")
    ]
