from django.db import models

from pretalx.common.mixins import LogMixin


class Availability(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='availabilities',
        on_delete=models.PROTECT,
    )
    person = models.ForeignKey(
        to='person.User',
        related_name='availabilities',
        on_delete=models.PROTECT,
        null=True, blank=True,
    )
    room = models.ForeignKey(
        to='schedule.Room',
        related_name='availabilities',
        on_delete=models.PROTECT,
        null=True, blank=True,
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
