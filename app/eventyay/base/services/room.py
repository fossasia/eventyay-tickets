import logging
import sys

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.transaction import atomic
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import AuditLog, Channel, User
from eventyay.base.models.event import Event
from eventyay.base.models.room import (
    Room,
    RoomConfigSerializer,
    RoomView,
    get_room_with_linked_sessions,
    partial_validated_update,
)
from eventyay.base.services.stale_cache import invalidate_next_stream_cache
from eventyay.base.services.stale_cache import (
    NONE_SENTINEL,
    cache_delete,
    deserialize_none_sentinel,
    get_stale_cached,
)
from eventyay.base.services.user import get_public_users
from eventyay.base.signals import periodic_task
from eventyay.features.live.channels import GROUP_ROOM


logger = logging.getLogger(__name__)

CURRENT_STREAM_MAX_CACHE_TTL = 60
CURRENT_STREAM_STALE_CACHE_TTL = 3600
NEXT_STREAM_MAX_CACHE_TTL = 300
NEXT_STREAM_STALE_CACHE_TTL = 3600
CURRENT_STREAM_HTTP_MAX_AGE = 30
NEXT_STREAM_HTTP_MAX_AGE = 60


def current_stream_cache_key(room_id):
    return f'stream:current:{room_id}'


def current_stream_stale_cache_key(room_id):
    return f'stream:current:{room_id}:stale'


def next_stream_cache_key(room_id):
    return f'stream:next:{room_id}'


def next_stream_stale_cache_key(room_id):
    return f'stream:next:{room_id}:stale'


def invalidate_current_stream_cache(room_id):
    cache_delete(current_stream_cache_key(room_id), current_stream_stale_cache_key(room_id))
    invalidate_next_stream_cache(room_id)


def _deserialize_cached_stream(cached):
    return deserialize_none_sentinel(cached)


def _load_current_stream_from_db(room):
    current = room.get_current_stream()
    if not current:
        return NONE_SENTINEL

    data = serialize_current_stream(current)
    return data


def get_cached_current_stream_data(room):
    """Return serialized current stream for a room, or None if idle."""
    cached = get_stale_cached(
        current_stream_cache_key(room.pk),
        current_stream_stale_cache_key(room.pk),
        lambda: _load_current_stream_from_db(room),
        CURRENT_STREAM_MAX_CACHE_TTL,
        CURRENT_STREAM_STALE_CACHE_TTL,
        log_context=f'current stream room {room.pk}',
    )
    return _deserialize_cached_stream(cached)


def _load_next_stream_from_db(room):
    upcoming = room.get_next_stream()
    if not upcoming:
        return NONE_SENTINEL
    return serialize_current_stream(upcoming)


def get_cached_next_stream_data(room):
    """Return serialized next stream for a room, or None if none scheduled."""
    cached = get_stale_cached(
        next_stream_cache_key(room.pk),
        next_stream_stale_cache_key(room.pk),
        lambda: _load_next_stream_from_db(room),
        NEXT_STREAM_MAX_CACHE_TTL,
        NEXT_STREAM_STALE_CACHE_TTL,
        log_context=f'next stream room {room.pk}',
    )
    return _deserialize_cached_stream(cached)


def serialize_current_stream(current):
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


@database_sync_to_async
def start_view(room: Room, user: User, delete=False):
    # The majority of RoomViews that go "abandoned" (i.e. ``end`` is never set) are likely caused by server
    # crashes or restarts, in which case ``end`` can't be set. However, after a server crash, the client
    # either reconnects automatically or the user will attempt a reconnect themselves through a page reload,
    # so the most likely end of the previous session is "just before this", and the best assumption is to set
    # the end to "now".
    #
    # Obviously, this is wrong whenever a user has multiple sessions open, e.g. if the same user has the room
    # open in browser A and then opens the same room in browser B, this will set the ``end`` for the session
    # in browser A, even though it's already running. It doesn't matter, though! First, for all our statistics
    # we only count unique users and the result "this user was present at the time" is still correct. Second,
    # the way ``end_view`` is implemented, the session from browser A will still be corrected with the accurate
    # time as soon as browser A leaves.
    previous = RoomView.objects.filter(room=room, user=user, end__isnull=True)
    if delete:
        previous.delete()
    else:
        previous.update(end=now())
    r = RoomView.objects.create(room=room, user=user)
    c = RoomView.objects.filter(room=room, end__isnull=True).values("user_id").distinct().count()
    return r, c


@database_sync_to_async
def end_view(view: RoomView, delete=False):
    if delete:
        if view.pk:
            view.delete()
    else:
        view.end = now()
        view.save()
    c = RoomView.objects.filter(room_id=view.room_id, end__isnull=True).values("user_id").distinct().count()
    is_last = RoomView.objects.filter(room_id=view.room_id, end__isnull=True, user=view.user).count() == 0
    return c, is_last


async def get_viewers(event: Event, room: Room, *, include_private=False):
    users = await get_public_users(
        # We're doing an ORM query in an async method, but it's okay, since it is not going to be evaluated but
        # lazily passed to get_public_users which will use it as a subquery :)
        ids=RoomView.objects.filter(room=room, end__isnull=True).values_list('user_id', flat=True),
        event_id=event.pk,
        include_banned=False,
        trait_badges_map=event.config.get('trait_badges_map'),
        require_show_publicly=not include_private,
    )
    return users


def validate_room_config_patch(room, body):
    """
    Validate a partial room config update in a sync DB context.

    Returns (validated_data, update_fields) on success, or (None, None) if invalid.
    """
    serializer = RoomConfigSerializer(
        get_room_with_linked_sessions(room),
        data=body,
        partial=True,
    )
    if "module_config" in body:
        _sanitize_jitsi_config(body["module_config"])
    return partial_validated_update(serializer, body)


def _sanitize_jitsi_config(module_config):
    if not isinstance(module_config, list):
        return
    for module in module_config:
        if not isinstance(module, dict):
            continue
        if module.get("type") != "call.jitsi":
            continue
        config = module.setdefault("config", {})
        if not isinstance(config, dict):
            config = {}
            module["config"] = config
        for key in ("domain", "jwt_enabled", "app_id", "key_id", "app_secret"):
            config.pop(key, None)


def uses_schedule_driven_stage(module_config):
    stage_modules = {
        'livestream.native',
        'livestream.youtube',
    }
    for module in module_config or []:
        if module.get('type') not in stage_modules:
            continue
        config = module.get('config') or {}
        return config.get('playback_mode') == 'schedule_driven'
    return False


def clear_stream_schedules_unless_schedule_driven(room):
    if uses_schedule_driven_stage(room.module_config):
        return False
    if not room.stream_schedules.exists():
        return False
    room.stream_schedules.all().delete()
    async_to_sync(broadcast_stream_change)(room.pk, None, reload=True)
    return True


@database_sync_to_async
@atomic
def save_room(event, room, update_fields, old_data, by_user):
    room.save(update_fields=update_fields)
    if 'module_config' in update_fields:
        clear_stream_schedules_unless_schedule_driven(room)
        from eventyay.agenda.views.utils import clear_schedule_caches

        with scope(event=event):
            clear_schedule_caches(event)
    new = RoomConfigSerializer(room).data

    AuditLog.objects.create(
        event_id=event.id,
        user=by_user,
        type='event.room.updated',
        data={
            'object': str(room.id),
            'old': old_data,
            'new': new,
        },
    )

    if 'chat.native' in {m['type'] for m in room.module_config}:
        Channel.objects.get_or_create(event_id=event.pk, room=room)
    return new


@database_sync_to_async
@atomic
def delete_room(event, room, by_user):
    room.deleted = True
    room.save(update_fields=['deleted'])
    old = RoomConfigSerializer(room).data

    AuditLog.objects.create(
        event_id=event.id,
        user=by_user,
        type='event.room.deleted',
        data={
            'object': str(room.id),
            'old': old,
        },
    )


@database_sync_to_async
@atomic
def reorder_rooms(event, id_list, by_user):
    id_list_str = [str(i) for i in id_list]

    def key(r):
        try:
            return id_list_str.index(str(r.id)), r.sorting_priority, r.name
        except ValueError:
            return sys.maxsize, r.sorting_priority, r.name

    all_rooms = list(
        event.rooms.filter(deleted=False).only('id', 'name', 'sorting_priority', 'position')
    )
    all_rooms.sort(key=key)
    to_update = []

    for i, r in enumerate(all_rooms):
        changed = False
        if i + 1 != r.sorting_priority:
            r.sorting_priority = i + 1
            changed = True
        if i != r.position:
            r.position = i
            changed = True
        if changed:
            to_update.append(r)

    Room.objects.bulk_update(to_update, fields=['sorting_priority', 'position'])

    AuditLog.objects.create(
        event_id=event.id,
        user=by_user,
        type='event.room.reorder',
        data={
            'id_list': id_list,
        },
    )


@atomic
def normalize_after_priority_change(event, room_id, new_priority):
    other_rooms = list(
        event.rooms.filter(deleted=False)
        .exclude(id=room_id)
        .only("id", "sorting_priority", "position")
        .order_by("sorting_priority", "id")
    )
    insert_pos = max(0, min(new_priority - 1, len(other_rooms)))
    actual_priority = insert_pos + 1
    ordered_all = other_rooms[:insert_pos] + [None] + other_rooms[insert_pos:]

    to_update = []
    for i, r in enumerate(ordered_all):
        if r is not None:
            expected_priority = i + 1
            expected_position = i
            changed = False
            if r.sorting_priority != expected_priority:
                r.sorting_priority = expected_priority
                changed = True
            if r.position != expected_position:
                r.position = expected_position
                changed = True
            if changed:
                to_update.append(r)

    if to_update:
        Room.objects.bulk_update(to_update, fields=["sorting_priority", "position"])

    Room.objects.filter(id=room_id).update(
        sorting_priority=actual_priority,
        position=actual_priority - 1,
    )


async def broadcast_stream_change(room_id, stream_schedule, reload=False):
    from eventyay.api.serializers.stream_schedule import StreamScheduleSerializer

    data = None
    if stream_schedule:
        serializer = StreamScheduleSerializer(stream_schedule)
        data = serializer.data

    await get_channel_layer().group_send(
        GROUP_ROOM.format(id=room_id),
        {
            'type': 'stream.change',
            'stream': data,
            'reload': reload,
        },
    )


@receiver(signal=periodic_task)
@scopes_disabled()
def check_stream_schedule_changes(sender, **kwargs):

    # Keep the last broadcast marker stable across periodic runs to avoid repeated rebroadcasts.
    cache_timeout = None

    rooms = Room.objects.filter(deleted=False, stream_schedules__isnull=False).select_related('event').distinct()

    for room in rooms:
        current_stream = room.get_current_stream()
        cache_key = f'room:{room.pk}:last_broadcast_stream'
        last_broadcast_id = cache.get(cache_key)

        current_stream_id = current_stream.pk if current_stream else None

        if current_stream_id != last_broadcast_id:
            cache.set(cache_key, current_stream_id, cache_timeout)
            async_to_sync(broadcast_stream_change)(room.pk, current_stream, reload=current_stream_id is None)
