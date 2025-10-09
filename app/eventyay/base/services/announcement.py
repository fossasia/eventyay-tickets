from channels.db import database_sync_to_async
from django.db.models import Q
from django.utils.timezone import now

from eventyay.base.models.announcement import Announcement


@database_sync_to_async
def create_announcement(**kwargs):
    return Announcement.objects.create(
        **{key: value for key, value in kwargs.items() if value is not None}
    ).serialize_public()


@database_sync_to_async
def get_announcement(pk, event):
    return Announcement.objects.get(pk=pk, event=event).serialize_public()


@database_sync_to_async
def get_announcements(event, moderator=False, **kwargs):
    announcements = Announcement.objects.filter(event=event)

    if not moderator:
        announcements = announcements.filter(
            Q(show_until__isnull=True) | Q(show_until__gt=now()),
            state=Announcement.States.ACTIVE,
        )
    return [announcement.serialize_public() for announcement in announcements]


@database_sync_to_async
def update_announcement(**kwargs):
    announcement = Announcement.objects.get(
        pk=kwargs.pop("id"), event=kwargs.pop("event")
    )
    permitted_fields = {
        field.name
        for field in Announcement._meta.get_fields()
        if field.name not in ("id", "event")
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
