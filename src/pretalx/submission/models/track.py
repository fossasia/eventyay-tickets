from django.db import models
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls


class Track(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event', on_delete=models.PROTECT, related_name='tracks'
    )
    name = I18nCharField(max_length=200)
    color = models.CharField(max_length=7)

    class urls(EventUrls):
        base = edit = '{self.event.cfp.urls.tracks}/{self.pk}'
        delete = '{base}/delete'

    def __str__(self) -> str:
        return str(self.name)
