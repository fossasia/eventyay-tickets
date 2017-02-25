from django.db import models


class Schedule(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    version = models.CharField(
        max_length=200,
        null=True, blank=True,
    )
