from django.db import models
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin


class EventPermission(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='permissions',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        to='person.User',
        related_name='permissions',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    is_orga = models.BooleanField(
        default=True,
        verbose_name=_('Organizes the event'),
    )
    is_reviewer = models.BooleanField(
        default=False,
        verbose_name=_('May write reviews for this event'),
    )
    review_override_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Override votes for reviews'),
        help_text=_('How many times may this user cast an overriding votes or vetos?'),
    )
    invitation_token = models.CharField(
        max_length=255,
        null=True, blank=True,
    )
    invitation_email = models.EmailField(
        null=True, blank=True,
    )

    def __str__(self):
        return '{} on {}'.format(self.user, self.event)
