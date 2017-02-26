from django.db import models


class Track(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='tracks',
    )
    name = models.CharField(
        max_length=200,
    )
    color = models.CharField(
        max_length=7,
    )

    def __str__(self):
        return str(self.name)
