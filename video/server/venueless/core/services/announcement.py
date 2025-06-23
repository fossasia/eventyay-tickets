from channels.db import database_sync_to_async
from django.db.models import Q
from django.utils.timezone import now

from venueless.core.models.announcement import Announcement


@database_sync_to_async
def create_announcement(**kwargs):
    return Announcement.objects.create(
        **{key: value for key, value in kwargs.items() if value is not None}
    ).serialize_public()


@database_sync_to_async
def get_announcement(pk, world):
    return Announcement.objects.get(pk=pk, world=world).serialize_public()


@database_sync_to_async
def get_announcements(world, moderator=False, **kwargs):
    announcements = Announcement.objects.filter(world=world)

    if not moderator:
        announcements = announcements.filter(
            Q(show_until__isnull=True) | Q(show_until__gt=now()),
            state=Announcement.States.ACTIVE,
        )
    return [announcement.serialize_public() for announcement in announcements]


@database_sync_to_async
def update_announcement(**kwargs):
    announcement = Announcement.objects.get(
        pk=kwargs.pop("id"), world=kwargs.pop("world")
    )
    permitted_fields = {
        field.name
        for field in Announcement._meta.get_fields()
        if field.name not in ("id", "world")
    }
    new_state = kwargs.pop("state", None)
    if new_state and new_state in announcement.allowed_states:
        announcement.state = new_state
    for key, value in kwargs.items():
        if key in permitted_fields:
            setattr(announcement, key, value)
    announcement.save()
    announcement.refresh_from_db()
    return announcement.serialize_public()
