from django.db import models
from django.utils.timezone import now
from django.utils.translation import pgettext, ugettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField
from urlman import Urls

from pretalx.common.mixins import LogMixin


class CfP(LogMixin, models.Model):
    event = models.OneToOneField(
        to='event.Event',
        on_delete=models.PROTECT,
    )
    headline = I18nCharField(
        max_length=300,
        null=True, blank=True,
        verbose_name=_('headline'),
    )
    text = I18nTextField(
        null=True, blank=True,
        verbose_name=_('text'),
        help_text=_('You can use markdown here.'),
    )
    default_type = models.ForeignKey(
        to='submission.SubmissionType',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('Default submission type'),
    )
    deadline = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('deadline'),
        help_text=_('Please put in the last date you want to accept submissions from users.'),
    )

    class urls(Urls):
        base = '{self.event.orga_urls.cfp}'
        questions = '{base}/questions'
        new_question = '{questions}/new'
        text = '{base}/text'
        edit_text = '{text}/edit'
        types = '{base}/types'
        new_type = '{types}/new'

    @property
    def is_open(self):
        if self.deadline is not None:
            return now() <= self.deadline
        return True

    def __str__(self) -> str:
        return str(self.headline)
