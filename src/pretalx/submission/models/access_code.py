from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.mixins.models import GenerateCode


class SubmitterAccessCode(LogMixin, GenerateCode, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.CASCADE,
        related_name='submitter_access_codes',
    )
    code = models.CharField(
        verbose_name=_('Access code'),
        max_length=255, default=GenerateCode.assign_code,
        db_index=True,
    )
    track = models.ForeignKey(
        to='submission.Track',
        on_delete=models.CASCADE,
        verbose_name=_('Track'),
        help_text=_('You can restrict the access code to a single track, or leave it open for all tracks.'),
        related_name='submitter_access_codes',
        null=True, blank=True,
    )
    submission_type = models.ForeignKey(
        to='submission.SubmissionType',
        on_delete=models.CASCADE,
        verbose_name=_('Submission Type'),
        help_text=_('You can restrict the access code to a single submission type, or leave it open for all tracks.'),
        related_name='submitter_access_codes',
        null=True, blank=True,
    )
    valid_until = models.DateTimeField(
        verbose_name=_('Valid until'),
        help_text=_('You can set or change this date later to make the access code unusable.'),
        null=True, blank=True,
    )
    maximum_uses = models.PositiveIntegerField(
        verbose_name=_('Maximum uses'),
        help_text=_('Numbers of times this access code can be used to submit a proposal.'),
        default=1,
        null=True, blank=True,
    )
    redeemed = models.PositiveIntegerField(default=0)

    _code_length = 20

    class Meta:
        unique_together = (('event', 'code'), )

    @property
    def is_valid(self):
        return now() < self.valid_until if self.valid_until else True
