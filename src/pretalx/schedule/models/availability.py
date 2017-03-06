from django.db import models


class Availability(models.Model):
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
