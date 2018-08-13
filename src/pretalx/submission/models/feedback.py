from django.db import models
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.phrases import phrases


class Feedback(LogMixin, models.Model):
    talk = models.ForeignKey(
        to='submission.Submission',
        related_name='feedback',
        on_delete=models.PROTECT,
        verbose_name=_('Talk'),
    )
    speaker = models.ForeignKey(
        to='person.User',
        related_name='feedback',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_('Speaker'),
    )
    rating = models.IntegerField(null=True, blank=True, verbose_name=_('Rating'))
    review = models.TextField(
        verbose_name=_('Review'), help_text=phrases.base.use_markdown
    )

    def __str__(self):
        """Help when debugging."""
        return f'Feedback(event={self.talk.event.slug}, talk={self.talk.title}, rating={self.rating})'
