import pytz
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField

from pretalx.common.models.settings import settings_hierarkey


@settings_hierarkey.add()
class Event(models.Model):
    name = I18nCharField(
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
    subtitle = I18nCharField(
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
    date_from = models.DateField(
        null=True, blank=True,
        verbose_name=_('Event start date'),
    )
    date_to = models.DateField(
        null=True, blank=True,
        verbose_name=_('Event end date'),
    )
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
    locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    locale = models.CharField(max_length=32, default=settings.LANGUAGE_CODE,
                              choices=settings.LANGUAGES,
                              verbose_name=_('Default language'))
    # enable_feedback = models.BooleanField(default=False)
    # send_notifications = models.BooleanField(default=True)

    def __str__(self) -> str:
        return str(self.name)

    @property
    def locales(self) -> list:
        return self.locale_array.split(",")

    def get_cfp(self) -> 'submission.CfP':
        if hasattr(self, 'cfp'):
            return self.cfp

        from pretalx.submission.models import CfP, Submission, SubmissionType
        sub_type = Submission.objects.filter(event=self).first()
        if not sub_type:
            sub_type = SubmissionType.objects.create(event=self, name='Talk')
        return CfP.objects.create(event=self, default_type=sub_type)

    def get_mail_backend(self, force_custom: bool=False) -> BaseEmailBackend:
        from pretalx.common.mail import CustomSMTPBackend

        if self.settings.smtp_use_custom or force_custom:
            return CustomSMTPBackend(host=self.settings.smtp_host,
                                     port=self.settings.smtp_port,
                                     username=self.settings.smtp_username,
                                     password=self.settings.smtp_password,
                                     use_tls=self.settings.smtp_use_tls,
                                     use_ssl=self.settings.smtp_use_ssl,
                                     fail_silently=False)
        else:
            return get_connection(fail_silently=False)
