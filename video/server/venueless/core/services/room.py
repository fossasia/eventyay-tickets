from channels.db import database_sync_to_async
from django.db.transaction import atomic
from django.utils.timezone import now

from venueless.core.models import AuditLog, Channel, User
from venueless.core.models.room import Room, RoomConfigSerializer, RoomView


@database_sync_to_async
def start_view(room: Room, user: User):
    return RoomView.objects.create(room=room, user=user)


@database_sync_to_async
def end_view(view: RoomView):
    view.end = now()
    view.save()


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
