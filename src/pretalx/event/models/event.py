from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Event(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name=_('Name'),
    )
    slug = models.SlugField(
        max_length=50, db_index=True,
        help_text=_(
            'Should be short, only contain lowercase letters and numbers, and must be unique among your events. '
            'This will be used in order codes, invoice numbers, links and bank transfer references.'),
        validators=[
            RegexValidator(
                regex="^[a-zA-Z0-9.-]+$",
                message=_('The slug may only contain letters, numbers, dots and dashes.'),
            ),
        ],
        verbose_name=_("Short form"),
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_('Event is public')
    )
    permitted = models.ManyToManyField(
        to='person.User',
        through='person.EventPermission',
        related_name="events",
    )
    date_from = models.DateTimeField(verbose_name=_("Event start time"))
    date_to = models.DateTimeField(null=True, blank=True,
                                   verbose_name=_("Event end time"))
