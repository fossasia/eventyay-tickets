from channels.db import database_sync_to_async
from django.db.transaction import atomic
from django.utils.timezone import now

from venueless.core.models import AuditLog, Channel, User
from venueless.core.models.room import Room, RoomConfigSerializer, RoomView


@database_sync_to_async
def start_view(room: Room, user: User):
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
    RoomView.objects.filter(room=room, user=user, end__isnull=True).update(end=now())
    r = RoomView.objects.create(room=room, user=user)
    c = RoomView.objects.filter(room=room, end__isnull=True).count()
    return r, c


@database_sync_to_async
def end_view(view: RoomView):
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
