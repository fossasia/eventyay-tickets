from django.db import models
from django.utils.translation import ugettext_lazy as _


class EventPermission(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='permissions',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        to='person.User',
        related_name='permissions',
        on_delete=models.CASCADE,
    )
    is_orga = models.BooleanField(
        default=True,
        verbose_name=_('Organizes the event'),
    )

    def __str__(self):
        return '{} on {}'.format(self.user, self.event)
