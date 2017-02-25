from django.db import models


class Room(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='rooms',
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.CharField(
        max_length=1000,
        null=True, blank=True,
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True,
    )
    order = models.PositiveIntegerField(
        null=True, blank=True,
    )
