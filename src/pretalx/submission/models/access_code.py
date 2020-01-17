import math

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.mixins.models import GenerateCode
from pretalx.common.urls import EventUrls


class SubmitterAccessCode(LogMixin, GenerateCode, models.Model):
    event = models.ForeignKey(
        to="event.Event",
        on_delete=models.CASCADE,
        related_name="submitter_access_codes",
    )
    code = models.CharField(
        verbose_name=_("Access code"), max_length=255, db_index=True,
    )
    track = models.ForeignKey(
        to="submission.Track",
        on_delete=models.CASCADE,
        verbose_name=_("Track"),
        help_text=_(
            "You can restrict the access code to a single track, or leave it open for all tracks."
        ),
        related_name="submitter_access_codes",
        null=True,
        blank=True,
    )
    submission_type = models.ForeignKey(
        to="submission.SubmissionType",
        on_delete=models.CASCADE,
        verbose_name=_("Submission Type"),
        help_text=_(
            "You can restrict the access code to a single submission type, or leave it open for all submission types."
        ),
        related_name="submitter_access_codes",
        null=True,
        blank=True,
    )
    valid_until = models.DateTimeField(
        verbose_name=_("Valid until"),
        help_text=_(
            "You can set or change this date later to invalidate the access code."
        ),
        null=True,
        blank=True,
    )
    maximum_uses = models.PositiveIntegerField(
        verbose_name=_("Maximum uses"),
        help_text=_(
            "Numbers of times this access code can be used to submit a proposal. Leave empty for no limit."
        ),
        default=1,
        null=True,
        blank=True,
    )
    redeemed = models.PositiveIntegerField(default=0)

    _code_length = 32

    class Meta:
        unique_together = (("event", "code"),)

    class urls(EventUrls):
        edit = "{self.event.cfp.urls.access_codes}{self.code}/"
        send = "{edit}send"
        delete = "{edit}delete"
        cfp_url = "{self.event.cfp.urls.public}?access_code={self.code}"

    @property
    def is_valid(self):
        time_valid = now() < self.valid_until if self.valid_until else True
        redemptions_valid = (
            self.maximum_uses - self.redeemed > 0 if self.maximum_uses else True
        )
        return time_valid and redemptions_valid

    @property
    def redemptions_left(self):
        if not self.maximum_uses:
            return math.inf
        return self.maximum_uses - self.redeemed

    def send_invite(self, to, subject, text):
        from pretalx.mail.models import QueuedMail

        to = to.split(",") if isinstance(to, str) else to
        for invite in to:
            QueuedMail(event=self.event, to=invite, subject=subject, text=text,).send()

    send_invite.alters_data = True
