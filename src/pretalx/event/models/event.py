import pytz
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
        help_text=_('Should be short, only contain lowercase letters and numbers, and must be unique.'),
        validators=[
            RegexValidator(
                regex="^[a-zA-Z0-9.-]+$",
                message=_('The slug may only contain letters, numbers, dots and dashes.'),
            ),
        ],
        verbose_name=_("Short form"),
    )
    subtitle = models.CharField(
        max_length=200,
        verbose_name=_('Subitle'),
        null=True, blank=True,
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
    date_from = models.DateField(verbose_name=_('Event start date'))
    date_to = models.DateField(null=True, blank=True,
                               verbose_name=_('Event end date'))
    timezone = models.CharField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        max_length=30,
        default='Europe/Berlin',
    )
    email = models.EmailField(
        verbose_name=_('Orga email address'),
        help_text=_('Will be used as sender/reply-to in emails'),
        null=True, blank=True,
    )
    color = models.CharField(
        max_length=7,
        verbose_name=_('Main event color'),
        help_text=_('Please provide a hex value like #00ff00 if you do not like pretalx colors.'),
        null=True, blank=True,
        validators=[],
    )
    # enable_feedback = models.BooleanField(default=False)
    # send_notifications = models.BooleanField(default=True)

    def __str__(self):
        return str(self.name)