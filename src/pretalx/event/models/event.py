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
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mixins import LogMixin
from pretalx.common.models.settings import settings_hierarkey
from pretalx.common.urls import EventUrls, get_base_url

SLUG_CHARS = 'a-zA-Z0-9.-'


def event_css_path(instance, filename):
    return f'{instance.slug}/css/{filename}'


def event_logo_path(instance, filename):
    return f'{instance.slug}/img/{filename}'


@settings_hierarkey.add()
class Event(LogMixin, models.Model):
    name = I18nCharField(
        max_length=200,
        verbose_name=_('Name'),
    )
    slug = models.SlugField(
        max_length=50, db_index=True,
        validators=[
            RegexValidator(
                regex=f"^[{SLUG_CHARS}]+$",
                message=_('The slug may only contain letters, numbers, dots and dashes.'),
            ),
        ],
        verbose_name=_("Short form"),
        help_text=_('Should be short, only contain lowercase letters and numbers, and must be unique, as it is used in URLs.'),
    )
    subtitle = I18nCharField(
        max_length=200,
        null=True, blank=True,
        verbose_name=_('Subtitle'),
        help_text=_('A tagline, or motto, or description. Not mandatory.')
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
    )
    primary_color = models.CharField(
        max_length=7,
        null=True, blank=True,
        validators=[],
        verbose_name=_('Main event color'),
        help_text=_('Please provide a hex value like #00ff00 if you do not like pretalx colors.'),
    )
    custom_css = models.FileField(
        upload_to=event_css_path,
        null=True, blank=True,
        verbose_name=_('Custom Event CSS'),
        help_text=_('Upload a custom CSS file if changing the primary color is not sufficient for you.'),
    )
    logo = models.FileField(
        upload_to=event_logo_path,
        null=True, blank=True,
        verbose_name=_('Logo'),
        help_text=_('Upload your event\'s logo, if it is suitable to be displayed in the frontend\'s header.'),
    )
    locale_array = models.TextField(default=settings.LANGUAGE_CODE)
    locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_('Default language'),
    )
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
    question_template = models.ForeignKey(
        to='mail.MailTemplate', on_delete=models.CASCADE,
        related_name='+', null=True, blank=True,
    )
    landing_page_text = I18nTextField(
        verbose_name=_('Landing page text'),
        help_text=_('This text will be shown on the landing page, alongside with links to the CfP and schedule, if appropriate. You can use markdown here.'),
        null=True, blank=True,
    )
    plugins = models.TextField(
        null=True, blank=True,
        verbose_name=_('Plugins'),
    )

    class urls(EventUrls):
        base = '/{self.slug}'
        login = '{base}/login'
        logout = '{base}/logout'
        logo = '{self.logo.url}'
        reset = '{base}/reset'
        submit = '{base}/submit'
        user = '{base}/me'
        user_delete = '{base}/me/delete'
        user_submissions = '{user}/submissions'
        schedule = '{base}/schedule'
        changelog = '{schedule}/changelog'
        frab_xml = '{schedule}.xml'
        frab_json = '{schedule}.json'
        frab_xcal = '{schedule}.xcal'
        ical = '{schedule}.ics'
        feed = '{schedule}/feed.xml'
        export = '{schedule}/export'
        location = '{schedule}/location'

    class orga_urls(EventUrls):
        create = '/orga/event/new'
        base = '/orga/event/{self.slug}'
        cfp = '{base}/cfp'
        users = '{base}/users'
        mail = '{base}/mails'
        send_mails = '{mail}/send'
        mail_templates = '{mail}/templates'
        new_template = '{mail_templates}/new'
        outbox = '{mail}/outbox'
        sent_mails = '{mail}/sent'
        send_outbox = '{outbox}/send'
        purge_outbox = '{outbox}/purge'
        submissions = '{base}/submissions'
        submission_cards = '{base}/submissions/cards/'
        new_submission = '{submissions}/new'
        speakers = '{base}/speakers'
        settings = edit_settings = '{base}/settings'
        mail_settings = edit_mail_settings = '{settings}/mail'
        team_settings = '{settings}/team'
        room_settings = '{schedule}/rooms'
        new_room = '{room_settings}/new'
        schedule = '{base}/schedule'
        schedule_import = '{schedule}/import'
        schedule_export = '{schedule}/export'
        schedule_export_trigger = '{schedule_export}/trigger'
        schedule_export_download = '{schedule_export}/download'
        release_schedule = '{schedule}/release'
        reset_schedule = '{schedule}/reset'
        toggle_schedule = '{schedule}/toggle'
        reviews = '{base}/reviews'
        schedule_api = '{base}/schedule/api'
        rooms_api = '{schedule_api}/rooms'
        talks_api = '{schedule_api}/talks'
        plugins = '{base}/plugins'
        information = '{base}/info'
        new_information = '{base}/info/new'

    class api_urls(EventUrls):
        base = '/api/events/{self.slug}'
        submissions = '{base}/submissions'
        talks = '{base}/talks'
        schedules = '{base}/schedules'
        speakers = '{base}/speakers'

    def __str__(self) -> str:
        return f'Event(slug={self.slug}, date_from={self.date_from.isoformat()})'

    @property
    def locales(self) -> list:
        return self.locale_array.split(",")

    @property
    def named_locales(self) -> list:
        enabled = set(self.locale_array.split(","))
        return [a for a in settings.LANGUAGES_NATURAL_NAMES if a[0] in enabled]

    @property
    def html_export_url(self) -> str:
        return get_base_url(self) + self.orga_urls.schedule_export_download

    def save(self, *args, **kwargs):
        was_created = not bool(self.pk)
        super().save(*args, **kwargs)

        if was_created:
            self._build_initial_data()

    def get_plugins(self):
        if not self.plugins:
            return []
        return self.plugins.split(',')

    def _get_default_submission_type(self):
        from pretalx.submission.models import Submission, SubmissionType
        sub_type = Submission.objects.filter(event=self).first()
        if not sub_type:
            sub_type = SubmissionType.objects.create(event=self, name='Talk')
        return sub_type

    @cached_property
    def fixed_templates(self):
        return [self.accept_template, self.ack_template, self.reject_template, self.update_template]

    def _build_initial_data(self):
        from pretalx.mail.default_templates import ACCEPT_TEXT, ACK_TEXT, GENERIC_SUBJECT, REJECT_TEXT, UPDATE_TEXT, QUESTION_SUBJECT, QUESTION_TEXT
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
        self.question_template = self.question_template or MailTemplate.objects.create(event=self, subject=QUESTION_SUBJECT, text=QUESTION_TEXT)
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

    @property
    def reviews(self):
        from pretalx.submission.models import Review
        return Review.objects.filter(submission__event=self)

    @property
    def submission_questions(self):
        return self.questions.filter(target='submission')

    @cached_property
    def talks(self):
        from pretalx.submission.models import SubmissionStates
        return self.submissions.filter(models.Q(state=SubmissionStates.ACCEPTED) | models.Q(state=SubmissionStates.CONFIRMED))

    @cached_property
    def speakers(self):
        from pretalx.person.models import User
        return User.objects.filter(submissions__in=self.talks).order_by('id').distinct()

    @cached_property
    def submitters(self):
        from pretalx.person.models import User
        return User.objects.filter(submissions__event=self).order_by('id').distinct()

    def release_schedule(self, name, user=None):
        self.wip_schedule.freeze(name=name, user=user)

    def send_orga_mail(self, text, stats=False):
        from django.utils.translation import override
        from pretalx.common.mail import mail_send_task
        from pretalx.mail.models import QueuedMail
        ctx = {
            'event_dashboard': self.orga_urls.base.full(),
            'event_review': self.orga_urls.reviews.full(),
            'event_schedule': self.orga_urls.schedule.full(),
            'event_submissions': self.orga_urls.submissions.full(),
            'event_team': self.orga_urls.team_settings.full(),
            'submission_count': self.submissions.all().count(),
        }
        if stats:
            ctx.update({
                'talk_count': self.current_schedule.talks.filter(is_visible=True).count(),
                'reviewer_count': self.permissions.filter(is_reviewer=True).count(),
                'review_count': self.reviews.count(),
                'schedule_count': self.schedules.count() - 1,
                'mail_count': self.queued_mails.filter(sent__isnull=False).count(),
            })
        with override(self.locale):
            text = str(text).format(**ctx) + '-- '
            text += _('''
This mail was sent to you by the content system of your event {name}.''').format(name=self.name)
        mail_send_task.apply_async(kwargs={
            'to': [self.email],
            'subject': _('[{slug}] News from your content system').format(slug=self.slug),
            'body': text,
            'html': QueuedMail.text_to_html(text, event=self),
            'sender': f'noreply@{settings.SITE_NETLOC}',
        })
