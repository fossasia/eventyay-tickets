import sys

from channels.db import database_sync_to_async
from django.db.transaction import atomic
from django.utils.timezone import now

from venueless.core.models import AuditLog, Channel, User
from venueless.core.models.room import Room, RoomConfigSerializer, RoomView


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
    c = RoomView.objects.filter(room=room, end__isnull=True).count()
    return r, c


@database_sync_to_async
def end_view(view: RoomView, delete=False):
    if delete:
        if view.pk:
            view.delete()
    else:
        view.end = now()
        view.save()
    c = RoomView.objects.filter(room_id=view.room_id, end__isnull=True).count()
    return c


@database_sync_to_async
@atomic
def save_room(world, room, update_fields, old_data, by_user):
    room.save(update_fields=update_fields)
    new = RoomConfigSerializer(room).data

    AuditLog.objects.create(
        world_id=world.id,
        user=by_user,
        type="world.room.updated",
        data={
            "object": str(room.id),
            "old": old_data,
            "new": new,
        },
    )

    if "chat.native" in set(m["type"] for m in room.module_config):
        Channel.objects.get_or_create(world_id=world.pk, room=room)
    return new


@database_sync_to_async
@atomic
def delete_room(world, room, by_user):
    room.deleted = True
    room.save(update_fields=["deleted"])
    old = RoomConfigSerializer(room).data

    AuditLog.objects.create(
        world_id=world.id,
        user=by_user,
        type="world.room.deleted",
        data={
            "object": str(room.id),
            "old": old,
        },
    )


@database_sync_to_async
@atomic
def reorder_rooms(world, id_list, by_user):
    def key(r):
        try:
            return id_list.index(str(r.id)), r.sorting_priority, r.name
        except:
            return sys.maxsize, r.sorting_priority, r.name

    all_rooms = list(
        world.rooms.filter(deleted=False).only("id", "name", "sorting_priority")
    )
    all_rooms.sort(key=key)
    to_update = []

    for i, r in enumerate(all_rooms):
        if i + 1 != r.sorting_priority:
            r.sorting_priority = i + 1
            to_update.append(r)

    Room.objects.bulk_update(to_update, fields=["sorting_priority"])

    AuditLog.objects.create(
        world_id=world.id,
        user=by_user,
        type="world.room.reorder",
        data={
            "id_list": id_list,
        },
    )
