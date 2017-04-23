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
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
