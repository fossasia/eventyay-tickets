from datetime import datetime, time

import pytz
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import RegexValidator
from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import make_aware
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField
from urlman import Urls

from pretalx.common.mixins import LogMixin
from pretalx.common.models.settings import settings_hierarkey


@settings_hierarkey.add()
class Event(LogMixin, models.Model):
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
        verbose_name=_('Event start date'),
    )
    date_to = models.DateField(
        verbose_name=_('Event end date'),
    )
    timezone = models.CharField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        max_length=30,
        default='UTC',
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
    accept_template = models.ForeignKey(
        to='mail.MailTemplate', on_delete=models.CASCADE,
        related_name='+', null=True, blank=True,
    )
    ack_template = models.ForeignKey(
        to='mail.MailTemplate', on_delete=models.CASCADE,
        related_name='+', null=True, blank=True,
    )
    reject_template = models.ForeignKey(
        to='mail.MailTemplate', on_delete=models.CASCADE,
        related_name='+', null=True, blank=True,
    )
    update_template = models.ForeignKey(
        to='mail.MailTemplate', on_delete=models.CASCADE,
        related_name='+', null=True, blank=True,
    )
    # enable_feedback = models.BooleanField(default=False)
    # send_notifications = models.BooleanField(default=True)

    class urls(Urls):
        base = '/{self.slug}'
        login = '{base}/login'
        logout = '{base}/logout'
        reset = '{base}/reset'
        submit = '{base}/submit'
        user = '{base}/me'
        user_submissions = '{user}/submissions'
        schedule = '{base}/schedule'
        changelog = '{schedule}/changelog'
        frab = '{schedule}.xml'
        feed = '{schedule}/feed.xml'
        location = '{schedule}/location'

    class orga_urls(Urls):
        create = '/orga/event/new'
        base = '/orga/event/{self.slug}'
        cfp = '{base}/cfp'
        users = '{base}/users'
        mail = '{base}/mails'
        send_mails = '{mail}/send'
        mail_templates = '{mail}/templates'
        new_template = '{mail_templates}/new'
        outbox = '{mail}/outbox'
        send_outbox = '{outbox}/send'
        purge_outbox = '{outbox}/purge'
        submissions = '{base}/submissions'
        submission_cards = '{base}/submissions/cards/'
        new_submission = '{submissions}/new'
        speakers = '{base}/speakers'
        settings = '{base}/settings'
        edit_settings = '{settings}/edit'
        mail_settings = '{settings}/mail'
        edit_mail_settings = '{mail_settings}/edit'
        team_settings = '{settings}/team'
        invite = '{team_settings}/add'
        room_settings = '{settings}/rooms'
        new_room = '{room_settings}/new'
        schedule = '{base}/schedule'
        release_schedule = '{schedule}/release'
        reset_schedule = '{schedule}/reset'

    class api_urls(Urls):
        base = '/orga/event/{self.slug}'
        schedule = '{base}/schedule/api'
        rooms = '{schedule}/rooms'
        talks = '{schedule}/talks'

    def __str__(self) -> str:
        return str(self.name)

    @property
    def locales(self) -> list:
        return self.locale_array.split(",")

    @property
    def named_locales(self) -> list:
        enabled = set(self.locale_array.split(","))
        return [a for a in settings.LANGUAGES_NATURAL_NAMES if a[0] in enabled]

    def save(self, *args, **kwargs):
        was_created = not bool(self.pk)
        super().save(*args, **kwargs)

        if was_created:
            self._build_initial_data()

    def _get_default_submission_type(self):
        from pretalx.submission.models import Submission, SubmissionType
        sub_type = Submission.objects.filter(event=self).first()
        if not sub_type:
            sub_type = SubmissionType.objects.create(event=self, name='Talk')
        return sub_type

    def _build_initial_data(self):
        from pretalx.mail.default_templates import ACCEPT_TEXT, ACK_TEXT, GENERIC_SUBJECT, REJECT_TEXT, UPDATE_TEXT
        from pretalx.mail.models import MailTemplate

        if not hasattr(self, 'cfp'):
            from pretalx.submission.models import CfP
            CfP.objects.create(event=self, default_type=self._get_default_submission_type())

        if not self.schedules.filter(version__isnull=True).exists():
            from pretalx.schedule.models import Schedule
            Schedule.objects.create(event=self)

        self.accept_template = self.accept_template or MailTemplate.objects.create(event=self, subject=GENERIC_SUBJECT, text=ACCEPT_TEXT)
        self.ack_template = self.ack_template or MailTemplate.objects.create(event=self, subject=GENERIC_SUBJECT, text=ACK_TEXT)
        self.reject_template = self.reject_template or MailTemplate.objects.create(event=self, subject=GENERIC_SUBJECT, text=REJECT_TEXT)
        self.update_template = self.update_template or MailTemplate.objects.create(event=self, subject=GENERIC_SUBJECT, text=UPDATE_TEXT)
        self.save()

    @cached_property
    def pending_mails(self):
        return self.queued_mails.filter(sent__isnull=True).count()

    @cached_property
    def wip_schedule(self):
        schedule, _ = self.schedules.get_or_create(version__isnull=True)
        return schedule

    @cached_property
    def current_schedule(self):
        return self.schedules.order_by('-published').filter(published__isnull=False).first()

    @property
    def duration(self):
        return (self.date_to - self.date_from).days + 1

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

    @property
    def event(self):
        return self

    @property
    def datetime_from(self):
        return make_aware(datetime.combine(
            self.date_from,
            time(hour=0, minute=0, second=0)
        ), pytz.timezone(self.timezone))

    @property
    def datetime_to(self):
        return make_aware(datetime.combine(
            self.date_to,
            time(hour=23, minute=59, second=59)
        ), pytz.timezone(self.timezone))

    def release_schedule(self, name, user=None):
        self.wip_schedule.freeze(name=name, user=user)
