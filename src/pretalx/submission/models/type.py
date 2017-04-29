from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField

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

    def __str__(self) -> str:
        return _('{name} ({duration} minutes)').format(
            name=self.name,
            duration=self.default_duration,
        )
