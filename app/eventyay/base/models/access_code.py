import math

from django.core import validators
from django.db import models
from django.utils.timezone import now
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from eventyay.common.urls import EventUrls
from eventyay.talk_rules.event import can_change_event_settings

from .mixins import GenerateCode, PretalxModel


class SubmitterAccessCode(GenerateCode, PretalxModel):
    event = models.ForeignKey(
        to='Event',
        on_delete=models.CASCADE,
        related_name='submitter_access_codes',
    )
    code = models.CharField(
        verbose_name=_('Access code'),
        max_length=255,
        db_index=True,
        validators=[validators.RegexValidator('^[a-zA-Z0-9]+$')],
    )
    track = models.ForeignKey(
        to='Track',
        on_delete=models.CASCADE,
        verbose_name=_('Track'),
        help_text=_('You can restrict the access code to a single track, or leave it open for all tracks.'),
        related_name='submitter_access_codes',
        null=True,
        blank=True,
    )
    submission_type = models.ForeignKey(
        to='SubmissionType',
        on_delete=models.CASCADE,
        verbose_name=_('Session Type'),
        help_text=_(
            'You can restrict the access code to a single session type, or leave it open for all session types.'
        ),
        related_name='submitter_access_codes',
        null=True,
        blank=True,
    )
    valid_until = models.DateTimeField(
        verbose_name=_('Valid until'),
        help_text=_('You can set or change this date later to invalidate the access code.'),
        null=True,
        blank=True,
    )
    maximum_uses = models.PositiveIntegerField(
        verbose_name=_('Maximum uses'),
        help_text=_('Numbers of times this access code can be used to submit a proposal. Leave empty for no limit.'),
        default=1,
        null=True,
        blank=True,
    )
    redeemed = models.PositiveIntegerField(default=0, editable=False)

    _code_length = 32

    log_prefix = 'pretalx.access_code'

    class Meta:
        unique_together = (('event', 'code'),)
        rules_permissions = {
            'list': can_change_event_settings,
            'view': can_change_event_settings,
            'create': can_change_event_settings,
            'update': can_change_event_settings,
            'delete': can_change_event_settings,
        }

    class urls(EventUrls):
        base = edit = '{self.event.cfp.urls.access_codes}{self.code}/'
        send = '{base}send'
        delete = '{base}delete/'
        cfp_url = '{self.event.cfp.urls.public}?access_code={self.code}'

    @property
    def log_parent(self):
        return self.event

    @property
    def is_valid(self):
        time_valid = now() < self.valid_until if self.valid_until else True
        redemptions_valid = self.maximum_uses - self.redeemed > 0 if self.maximum_uses else True
        return time_valid and redemptions_valid

    @property
    def redemptions_left(self):
        if not self.maximum_uses:
            return math.inf
        return self.maximum_uses - self.redeemed

    def send_invite(self, to, subject, text):
        from eventyay.base.models import QueuedMail

        to = to.split(',') if isinstance(to, str) else to
        for invite in to:
            QueuedMail(
                event=self.event,
                to=invite,
                subject=subject,
                text=text,
                locale=get_language(),
            ).send()

    send_invite.alters_data = True
