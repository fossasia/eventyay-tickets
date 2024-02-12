import uuid
from functools import cached_property

from django.db import models
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField

from pretalx.common.mixins.models import OrderedModel, PretalxModel
from pretalx.common.models.settings import GlobalSettings
from pretalx.common.urls import EventUrls


class Room(OrderedModel, PretalxModel):
    """A Room is an actual place where talks will be scheduled.

    The Room object stores some meta information. Most, like capacity,
    are not in use right now.
    """

    event = models.ForeignKey(
        to="event.Event", on_delete=models.PROTECT, related_name="rooms"
    )
    name = I18nCharField(max_length=100, verbose_name=_("Name"))
    guid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_("GUID"),
        help_text=_(
            "Unique identifier (UUID) to help external tools identify the room."
        ),
    )
    description = I18nCharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("A description for attendees, for example directions."),
    )
    speaker_info = I18nCharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_("Speaker Information"),
        help_text=_(
            "Information relevant for speakers scheduled in this room, for example room size, special directions, available adaptors for video input …"
        ),
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Capacity"),
        help_text=_("How many people can fit in the room?"),
    )
    position = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("position",)
        unique_together = ("event", "guid")

    class urls(EventUrls):
        settings_base = edit = "{self.event.orga_urls.room_settings}{self.pk}/"
        delete = "{settings_base}delete"
        up = "{settings_base}up"
        down = "{settings_base}down"

    def __str__(self) -> str:
        return str(self.name)

    @staticmethod
    def get_order_queryset(event):
        return event.rooms.all()

    @cached_property
    def uuid(self):
        """Either a UUID5 calculated from the submission code and the instance identifier;
        or GUID value of the room, if it was imported or set manually."""
        if self.guid:
            return self.guid

        if not self.pk:
            return ""

        return uuid.uuid5(GlobalSettings().get_instance_identifier(), f"room:{self.pk}")
