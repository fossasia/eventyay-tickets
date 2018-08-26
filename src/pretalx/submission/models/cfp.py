from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mixins import LogMixin
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls


class CfP(LogMixin, models.Model):
    event = models.OneToOneField(to='event.Event', on_delete=models.PROTECT)
    headline = I18nCharField(
        max_length=300, null=True, blank=True, verbose_name=_('headline')
    )
    text = I18nTextField(
        null=True,
        blank=True,
        verbose_name=_('text'),
        help_text=phrases.base.use_markdown,
    )
    default_type = models.ForeignKey(
        to='submission.SubmissionType',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('Default submission type'),
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('deadline'),
        help_text=_(
            'Please put in the last date you want to accept submissions from users.'
        ),
    )

    class urls(EventUrls):
        base = '{self.event.orga_urls.cfp}'
        questions = '{base}/questions'
        new_question = '{questions}/new'
        remind_questions = '{questions}/remind'
        text = edit_text = '{base}/text'
        types = '{base}/types'
        new_type = '{types}/new'
        public = '{self.event.urls.base}/cfp'
        submit = '{self.event.urls.base}/submit'

    def __str__(self) -> str:
        """Help with debugging."""
        return f'CfP(event={self.event.slug})'

    @cached_property
    def is_open(self):
        if self.deadline is None:
            return True
        return self.max_deadline >= now() if self.max_deadline else True

    @cached_property
    def max_deadline(self):
        deadlines = list(
            self.event.submission_types.filter(deadline__isnull=False).values_list(
                'deadline', flat=True
            )
        )
        if self.deadline:
            deadlines.append(self.deadline)
        return max(deadlines) if deadlines else None
