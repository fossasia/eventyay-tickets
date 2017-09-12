import math

from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField
from urlman import Urls

from pretalx.common.mixins import LogMixin


class SubmissionType(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='submission_types',
        on_delete=models.CASCADE,
    )
    name = I18nCharField(
        max_length=100,
    )
    default_duration = models.PositiveIntegerField(
        default=30,
        help_text='Default duration in minutes',
    )
    max_duration = models.PositiveIntegerField(
        default=60,
        help_text='Maximum duration in minutes',
    )

    class urls(Urls):
        base = '{self.event.cfp.urls.types}/{self.pk}'
        default = '{base}/default'
        edit = '{base}/edit'
        delete = '{base}/delete'

    def __str__(self) -> str:
        if self.default_duration > 60 * 24:
            return _('{name} ({duration} hours)').format(
                name=self.name,
                duration=math.ceil(self.default_duration / 60 / 24),
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
