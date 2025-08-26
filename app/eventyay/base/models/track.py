from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from eventyay.common.urls import EventUrls
from eventyay.talk_rules.agenda import is_agenda_visible
from eventyay.talk_rules.event import can_change_event_settings
from eventyay.talk_rules.submission import (
    is_cfp_open,
    orga_can_change_submissions,
    use_tracks,
)

from .mixins import OrderedModel, PretalxModel


class Track(OrderedModel, PretalxModel):
    """A track groups :class:`~pretalx.submission.models.submission.Submission`
    objects within an :class:`~pretalx.event.models.event.Event`, e.g. by
    topic.

    :param color: The track colour, in the format #012345.
    """

    event = models.ForeignKey(to='Event', on_delete=models.PROTECT, related_name='tracks')
    name = I18nCharField(
        max_length=200,
        verbose_name=_('Name'),
    )
    description = I18nTextField(
        verbose_name=_('Description'),
        blank=True,
    )
    color = models.CharField(
        max_length=7,
        verbose_name=_('Color'),
        validators=[
            RegexValidator('#([0-9A-Fa-f]{3}){1,2}'),
        ],
    )
    position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='The position field is used to determine the order that tracks are displayed in (lowest first).',
    )
    requires_access_code = models.BooleanField(
        verbose_name=_('Requires access code'),
        help_text=_('This track will only be shown to submitters with a matching access code.'),
        default=False,
    )

    log_prefix = 'pretalx.track'

    class Meta:
        ordering = ('position',)
        rules_permissions = {
            'list': use_tracks & (is_agenda_visible | orga_can_change_submissions),
            'view': use_tracks & (is_cfp_open | is_agenda_visible | orga_can_change_submissions),
            'orga_list': use_tracks & orga_can_change_submissions,
            'orga_view': use_tracks & orga_can_change_submissions,
            'create': use_tracks & can_change_event_settings,
            'update': use_tracks & can_change_event_settings,
            'delete': use_tracks & can_change_event_settings,
        }

    class urls(EventUrls):
        base = edit = '{self.event.cfp.urls.tracks}{self.pk}/'
        delete = '{base}delete/'
        prefilled_cfp = '{self.event.cfp.urls.public}?track={self.slug}'

    def __str__(self) -> str:
        return str(self.name)

    @property
    def log_parent(self):
        return self.event

    @staticmethod
    def get_order_queryset(event):
        return event.tracks.all()

    @property
    def slug(self) -> str:
        """The slug makes tracks more readable in URLs.

        It consists of the ID, followed by a slugified (and, in lookups,
        optional) form of the track name.
        """
        return f'{self.id}-{slugify(self.name)}'
