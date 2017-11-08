from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls


class SubmissionType(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='submission_types',
        on_delete=models.CASCADE,
    )
    name = I18nCharField(
        max_length=100,
        verbose_name=_('name'),
    )
    default_duration = models.PositiveIntegerField(
        default=30,
        verbose_name=_('default duration'),
        help_text=_('Default duration in minutes'),
    )
    max_duration = models.PositiveIntegerField(
        default=60,
        verbose_name=_('maximum duration'),
        help_text=_('Maximum duration in minutes'),
    )

    class urls(EventUrls):
        base = '{self.event.cfp.urls.types}/{self.pk}'
        default = '{base}/default'
        edit = '{base}/edit'
        delete = '{base}/delete'

    def __str__(self) -> str:
        if self.default_duration > 60 * 24:
            return _('{name} ({duration} days)').format(
                name=self.name,
                duration=round(self.default_duration / 60 / 24, 1),
            )
        if self.default_duration > 90:
            return _('{name} ({duration} hours)').format(
                name=self.name,
                duration=round(self.default_duration / 60, 1),
            )
        return _('{name} ({duration} minutes)').format(
            name=self.name,
            duration=self.default_duration,
        )
