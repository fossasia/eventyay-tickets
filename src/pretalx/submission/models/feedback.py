from django.db import models
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin


class Feedback(LogMixin, models.Model):
    talk = models.ForeignKey(
        to='submission.Submission',
        verbose_name=_('Talk'),
        related_name='feedback',
        on_delete=models.PROTECT,
    )
    speaker = models.ForeignKey(
        to='person.User',
        verbose_name=_('Speaker'),
        related_name='feedback',
        null=True, blank=True,
        on_delete=models.PROTECT,
    )
    rating = models.IntegerField(
        verbose_name=_('Rating'),
        null=True, blank=True,
    )
    review = models.TextField(
        verbose_name=_('Review'),
        help_text=_('You can use markdown here!'),
    )
