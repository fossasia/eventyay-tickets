from channels.db import database_sync_to_async
from django.utils.timezone import now

from venueless.core.models import User
from venueless.core.models.room import Room, RoomView


@database_sync_to_async
def start_view(room: Room, user: User):
    return RoomView.objects.create(room=room, user=user)


@database_sync_to_async
def end_view(view: RoomView):
    view.end = now()
    view.save()


@database_sync_to_async
def update_room(room: Room):
    room.save()
