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
from django.db.models import Count, Max, OuterRef, Q, Subquery
from eventyay.timezones import common_timezones
from rest_framework import serializers

from eventyay.base.models.audit import AuditLog
from eventyay.base.models.chat import Channel, ChatEvent, Membership
from eventyay.base.models.event import Event
from eventyay.base.models.room import Room, RoomConfigSerializer, RoomView
from eventyay.base.services.room_creation_gate import (
    SERVER_BACKED_ROOM_MODULE_TYPES,
    user_can_create_server_backed_room_during_development,
)
from eventyay.base.services.video_theme import build_video_theme_for_event
from eventyay.core.permissions import Permission


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
    iframe_blockers = serializers.JSONField(required=False, allow_null=True)
    track_room_views = serializers.BooleanField(required=False)
    track_event_views = serializers.BooleanField(required=False)
    live_features = serializers.DictField(required=False)
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


@database_sync_to_async
def _get_event(event_id):
    """Retrieve Event by primary key or slug."""
    if isinstance(event_id, str) and event_id.isdigit():
        return Event.objects.filter(Q(slug=event_id) | Q(id=int(event_id))).first()
    return Event.objects.filter(slug=event_id).first()


async def get_event(event_id):
    event = await _get_event(event_id)
    return event


def get_rooms(event, user):
    from django_scopes import scope

    with scope(event=event):
        qs = (
            event.rooms.filter(deleted=False)
            .with_has_linked_sessions()
            .order_by('sorting_priority', 'id')
            .prefetch_related("channel")
            .annotate(
                current_roomviews=Subquery(
                    RoomView.objects.filter(room_id=OuterRef("pk"), end__isnull=True)
                    .values("room_id")
                    .order_by()
                    .annotate(
                        c=Count("user_id", distinct=True)
                    )
                    .values("c")
                )
            )
        )
        if user:
            qs = qs.with_permission(event=event, user=user)
        rooms_list = list(qs)
        live_features = (getattr(event, 'config', None) or {}).get('live_features', {})
        if not live_features.get('chat_rooms', False):
            rooms_list = [r for r in rooms_list if not is_chat_channel_room(r)]
        return rooms_list


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


def serialize_stream_schedule(current):
    """Serialize a StreamSchedule instance for API/websocket payloads."""
    from eventyay.base.services import room as room_service

    serializer = getattr(room_service, 'serialize_current_stream', None)
    if serializer is not None:
        return serializer(current)

    def isoformat(value):
        return value.isoformat() if value else None

    return {
        'id': current.pk,
        'room': current.room_id,
        'title': current.title,
        'url': current.url,
        'start_time': isoformat(current.start_time),
        'end_time': isoformat(current.end_time),
        'stream_type': current.stream_type,
        'config': current.config,
        'created_at': isoformat(current.created_at),
        'updated_at': isoformat(current.updated_at),
    }


def get_room_current_stream_data(room, current=None):
    """Return current stream payload for websocket room config.

    Uses Redis-backed cache when available (#4992); falls back to a direct DB
    lookup so this PR can merge independently.
    """
    if current is not None:
        return serialize_stream_schedule(current)

    from eventyay.base.services import room as room_service

    getter = getattr(room_service, 'get_cached_current_stream_data', None)
    if getter is not None:
        return getter(room)
    current = room.get_current_stream()
    if not current:
        return None
    return serialize_stream_schedule(current)


def batch_room_current_stream_data(rooms):
    """Return current stream payloads for many rooms using one DB query."""
    from django.utils.timezone import now

    from eventyay.base.models.stream_schedule import StreamSchedule

    room_ids = [room.pk for room in rooms]
    if not room_ids:
        return {}

    at_time = now()
    schedules = StreamSchedule.objects.filter(
        room_id__in=room_ids,
        start_time__lte=at_time,
        end_time__gt=at_time,
    ).order_by('room_id', 'start_time')

    active_by_room = {}
    for schedule in schedules:
        if schedule.room_id not in active_by_room:
            active_by_room[schedule.room_id] = schedule

    return {
        room_id: serialize_stream_schedule(schedule)
        for room_id, schedule in active_by_room.items()
    }


_UNSET = object()

_MEDIA_MODULE_TYPES = frozenset({
    'livestream.native',
    'livestream.youtube',
    'call.bigbluebutton',
    'call.janus',
    'call.zoom',
    'call.jitsi',
    'networking.roulette',
    'page.landing',
})


def is_chat_channel_room(room):
    modules = room.module_config or []
    if not isinstance(modules, list) or not modules:
        return False
    types = [module.get('type') for module in modules if isinstance(module, dict)]
    return 'chat.native' in types and not any(module_type in _MEDIA_MODULE_TYPES for module_type in types)


def count_chat_participants(channel_id):
    member_ids = Membership.objects.filter(
        channel_id=channel_id,
        user_id__isnull=False,
    ).values_list("user_id", flat=True)
    sender_ids = ChatEvent.objects.filter(
        channel_id=channel_id,
        sender_id__isnull=False,
    ).values_list("sender_id", flat=True)
    return len(set(member_ids) | set(sender_ids))


def get_room_config(room, permissions, *, current_stream=_UNSET):
    str_permissions = [p if isinstance(p, str) else getattr(p, "value", p) for p in permissions]
    if current_stream is _UNSET:
        stream_data = get_room_current_stream_data(room)
    else:
        stream_data = current_stream
    room_config = {
        "id": str(room.id),
        "name": room.name,
        "description": room.description,
        "picture": room.picture.url if room.picture else None,
        "import_id": room.import_id,
        "pretalx_id": room.pretalx_id,
        "permissions": [p for p in str_permissions if not p.startswith("event:")],
        "force_join": room.force_join,
        "modules": [],
        "schedule_data": room.schedule_data or None,
        "currentStream": stream_data,
    }

    if is_chat_channel_room(room):
        try:
            room_config["users"] = count_chat_participants(room.channel.id)
        except Channel.DoesNotExist:
            room_config["users"] = 0
    elif hasattr(room, "current_roomviews"):
        room_config["users"] = room.current_roomviews or 0
    else:
        room_config["users"] = 0

    for module in room.module_config:
        module_config = copy.deepcopy(module)
        if module["type"] == "call.bigbluebutton":
            module_config["config"] = {}
        elif module["type"] == "call.jitsi":
            cfg = module_config.get("config")
            if isinstance(cfg, dict):
                cfg.pop("domain", None)
                cfg.pop("jwt_enabled", None)
                cfg.pop("app_id", None)
                cfg.pop("key_id", None)
                cfg.pop("app_secret", None)
        elif module["type"] == "chat.native":
            # Strip webhook secrets — these are server-side only
            cfg = module_config.get("config")
            if isinstance(cfg, dict):
                cfg.pop("webhook_hmac_secret", None)
            if getattr(room, "channel", None):
                module_config["channel_id"] = str(room.channel.id)
        room_config["modules"].append(module_config)
    return room_config


def get_event_config_for_user(event, user):
    permissions = event.get_all_permissions(user)
    cfg = event.config or {}
    # Only expose schedule import-related pretalx config keys to the frontend.
    # (The legacy eventyay-talk connection keys like domain/event/connected/pushed were removed.)
    pretalx_cfg = (cfg.get("pretalx") or {})
    pretalx_public = {k: pretalx_cfg.get(k) for k in ("url", "conftool") if k in pretalx_cfg}

    world_block = {
        "id": str(event.id),
        "title": getattr(event, "title", getattr(event, "name", "")),
        "slug": getattr(event, "slug", str(event.id)),
        "organizer_slug": getattr(event.organizer, "slug", None) if hasattr(event, "organizer") and event.organizer else None,
        "timezone": event.settings.timezone,
        "date_from": event.date_from.isoformat() if event.date_from else None,
        "date_to": event.date_to.isoformat() if event.date_to else None,
        "visible_logo_url": event.visible_logo_url,
        "visible_header_image_url": event.visible_header_image_url,
        "pretalx": pretalx_public,
        "track_event_views": cfg.get("track_event_views", True),
        "track_video_event_views": cfg.get("track_event_views", True),
        "live_features": {
            "chat_rooms": False,
            "kiosks": False,
            "direct_messaging": False,
            "announcements": True,
            **(cfg.get("live_features") or {}),
        },
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
        elif p == "event.update":
            world_aliases.append("world:update")
        elif p.startswith("event:"):
            world_aliases.append("world:" + p[len("event:"):])
        elif p == "world:view":
            world_aliases.append("event.view")
        elif p == "world:update":
            world_aliases.append("event.update")
        elif p.startswith("world:"):
            world_aliases.append("event:" + p[len("world:"):])
    merged_permissions = sorted(set(event_perm_values) | set(world_aliases))

    result = {
        # Provide both keys for compatibility: frontend expects 'world', prior code used 'event'
        "world": world_block,
        "event": world_block,
        "permissions": merged_permissions,
        "rooms": [],
    }

    rooms = get_rooms(event, user)
    stream_data_by_room = batch_room_current_stream_data(rooms)
    for room in rooms:
        result["rooms"].append(
            get_room_config(
                room,
                permissions[event] | permissions[room],
                current_stream=stream_data_by_room.get(room.pk),
            )
        )
    return result


@database_sync_to_async
@transaction.atomic()
def _create_room(data, with_channel=False, permission_preset="public", creator=None):
    if "sorting_priority" not in data:
        data["sorting_priority"] = (
            Room.objects.filter(event=data["event"], deleted=False).aggregate(
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
    livestream_types = {
        "livestream.native",
        "livestream.youtube",
    }
    livestream_modules = [
        m for m in data.get("modules", []) if m.get("type") in livestream_types
    ]

    if types & SERVER_BACKED_ROOM_MODULE_TYPES:
        if not await user_can_create_server_backed_room_during_development(creator):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )

    if livestream_modules:
        allowed_stage_types = livestream_types | {"chat.native"}
        if len(livestream_modules) != 1 or types - allowed_stage_types:
            raise ValidationError(
                f"The dynamic creation of rooms with the modules {types} is currently not allowed.",
                code="invalid",
            )
        if not await event.has_permission_async(
            user=creator, permission=Permission.EVENT_ROOMS_CREATE_STAGE
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )

        module = livestream_modules[0]
        config = module.get("config", {}) or {}
        playback_mode = config.get("playback_mode") or "always_on"
        if playback_mode not in {"schedule_driven", "always_on"}:
            raise ValidationError(
                "Invalid stage playback mode.",
                code="invalid",
            )

        clean_config = {"playback_mode": playback_mode}
        if playback_mode == "always_on":
            if module["type"] == "livestream.native":
                clean_config["hls_url"] = config.get("hls_url", "")
            elif module["type"] == "livestream.youtube":
                clean_config["ytid"] = config.get("ytid", "")
                for key in (
                    "enablePrivacyEnhancedMode",
                    "loop",
                    "modestBranding",
                    "hideControls",
                    "noRelated",
                    "disableKb",
                    "showInfo",
                ):
                    if config.get(key):
                        clean_config[key] = True
        module["config"] = clean_config

        if "chat.native" in types:
            m = [m for m in data.get("modules", []) if m["type"] == "chat.native"][0]
            m["config"] = {"volatile": m.get("config", {}).get("volatile", False)}
    elif types == {"chat.native"}:
        live_features = (event.config or {}).get("live_features", {})
        if not live_features.get("chat_rooms", False):
            raise ValidationError(
                "Chat rooms are currently disabled.",
                code="chat_rooms_disabled",
            )
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
    elif types == {"call.jitsi"}:
        m = [m for m in data.get("modules", []) if m["type"] == "call.jitsi"][0]
        config = m.get("config", {})
        if not isinstance(config, dict):
            config = {}
        m["config"] = {
            "prefer_server": config.get("prefer_server", ""),
            "start_with_audio_muted": config.get(
                "start_with_audio_muted", False
            ),
            "start_with_video_muted": config.get(
                "start_with_video_muted", False
            ),
        }
    elif types == {"call.janus"}:
        if not await event.has_permission_async(
            user=creator, permission=Permission.EVENT_ROOMS_CREATE_BBB
        ):
            raise ValidationError(
                "This user is not allowed to create a room of this type.",
                code="denied",
            )
        m = [m for m in data.get("modules", []) if m["type"] == "call.janus"][0]
        m["config"] = {}
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
    return await database_sync_to_async(get_room_config)(
        room, permissions[room] | permissions[room.event]
    )


@database_sync_to_async
def generate_tokens(event, number, traits, days, by_user, long=False):
    from eventyay.base.models.auth import ShortToken
    jwt_config = event.config["JWT_secrets"][0]
    secret = jwt_config["secret"]
    audience = jwt_config["audience"]
    issuer = jwt_config["issuer"]
    iat = datetime.datetime.now(datetime.timezone.utc)
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
            "theme": build_video_theme_for_event(event),
            "title": getattr(event, "title", getattr(event, "name", "")),
            "locale": event.locale,
            "date_locale": cfg.get("date_locale", "en-ie"),
            "roles": event.roles,
            "bbb_defaults": bbb_defaults,
            "track_room_views": cfg.get("track_room_views", True),
            "track_event_views": cfg.get("track_event_views", True),
            "live_features": {
                "chat_rooms": False,
                "kiosks": False,
                "direct_messaging": False,
                "announcements": True,
                **(cfg.get("live_features") or {}),
            },
            "pretalx": cfg.get("pretalx", {}),
            "video_player": cfg.get("video_player"),
            "timezone": event.timezone,
            "trait_grants": event.trait_grants,
            "connection_limit": cfg.get("connection_limit", 0),
            "onsite_traits": cfg.get("onsite_traits", []),
            "conftool_url": cfg.get("conftool_url", ""),
            "conftool_password": cfg.get("conftool_password", ""),
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
