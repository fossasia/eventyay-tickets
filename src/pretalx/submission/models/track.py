from django.db import models
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin


class Track(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='tracks',
    )
    name = I18nCharField(
        max_length=200,
    )
    color = models.CharField(
        max_length=7,
    )

    def __str__(self) -> str:
        """Help when debugging."""
        return f'Track(event={self.event.slug}, name={self.name})'
