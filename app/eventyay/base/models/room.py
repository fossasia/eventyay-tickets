import uuid
from functools import cached_property

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField

from eventyay.base.models import GlobalSettings, OrderedModel, PretalxModel
from eventyay.common.urls import EventUrls
from eventyay.talk_rules.agenda import is_agenda_visible
from eventyay.talk_rules.event import can_change_event_settings
from eventyay.talk_rules.submission import orga_can_change_submissions


class Room(OrderedModel, PretalxModel):
    """A Room is an actual place where talks will be scheduled.

    The Room object stores some meta information. Most, like capacity,
    are not in use right now.
    """

    log_prefix = 'pretalx.room'

    event = models.ForeignKey(to='Event', on_delete=models.PROTECT, related_name='rooms')
    name = I18nCharField(max_length=100, verbose_name=_('Name'))
    guid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_('GUID'),
        help_text=_('Unique identifier (UUID) to help external tools identify the room.'),
    )
    description = I18nCharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('A description for attendees, for example directions.'),
    )
    speaker_info = I18nCharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_('Speaker Information'),
        help_text=_(
            'Information relevant for speakers scheduled in this room, for example room size, special directions, '
            'available adaptors for video input …'
        ),
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Capacity'),
        help_text=_('How many people can fit in the room?'),
    )
    position = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ('position',)
        unique_together = ('event', 'guid')
        rules_permissions = {
            'list': is_agenda_visible | orga_can_change_submissions,
            'view': is_agenda_visible | orga_can_change_submissions,
            'orga_list': orga_can_change_submissions,
            'orga_view': orga_can_change_submissions,
            'create': can_change_event_settings,
            'update': can_change_event_settings,
            'delete': can_change_event_settings,
        }

    class urls(EventUrls):
        settings_base = edit = '{self.event.orga_urls.room_settings}{self.pk}/'
        delete = '{settings_base}delete/'

    def __str__(self) -> str:
        return str(self.name)

    @property
    def log_parent(self):
        return self.event

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
            return ''

        return uuid.uuid5(GlobalSettings().get_instance_identifier(), f'room:{self.pk}')

    @property
    def slug(self) -> str:
        """The slug makes tracks more readable in URLs.

        It consists of the ID, followed by a slugified (and, in lookups,
        optional) form of the track name.
        """
        return f'{self.id}-{slugify(self.name)}'
