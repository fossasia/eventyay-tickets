from django.db import models
from i18nfield.fields import I18nCharField


class Track(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='tracks',
    )
    name = I18nCharField(
        max_length=200,
    )
    color = models.CharField(
        max_length=7,
    )

    def __str__(self) -> str:
        return str(self.name)
