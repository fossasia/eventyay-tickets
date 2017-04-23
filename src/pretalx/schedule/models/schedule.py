from django.db import models
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin


class Schedule(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    version = models.CharField(
        max_length=200,
        null=True, blank=True,
    )

    def __str__(self) -> str:
        return str(self.version) or _(f'Schedule for {self.event}')
