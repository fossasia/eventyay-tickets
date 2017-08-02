from django.db import models
from i18nfield.fields import I18nCharField
from urlman import Urls

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

    class Meta:
        ordering = ('position', )

    class urls(Urls):
        settings_base = '{self.event.orga_urls.room_settings}/{self.pk}'
        edit_settings = '{settings_base}/edit'
        delete = '{settings_base}/delete'

    def __str__(self) -> str:
        return str(self.name)
