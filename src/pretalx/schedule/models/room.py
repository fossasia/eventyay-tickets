from django.db import models
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin


class Room(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='rooms',
    )
    name = I18nCharField(
        max_length=100,
    )
    description = I18nCharField(
        max_length=1000,
        null=True, blank=True,
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True,
    )
    position = models.PositiveIntegerField(
        null=True, blank=True,
    )

    def __str__(self) -> str:
        return str(self.name)
