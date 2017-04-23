from django.db import models

from pretalx.common.mixins import LogMixin


class SpeakerProfile(LogMixin, models.Model):
    biography = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        to='person.User',
        related_name='profiles',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    event = models.ForeignKey(
        to='event.Event',
        related_name='+',
        on_delete=models.CASCADE,
    )
