from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls


class SpeakerProfile(LogMixin, models.Model):
    user = models.ForeignKey(
        to='person.User',
        related_name='profiles',
        on_delete=models.CASCADE,
        null=True, blank=True,
    )
    event = models.ForeignKey(
        to='event.Event',
        related_name='+',
        on_delete=models.CASCADE,
    )
    biography = models.TextField(
        verbose_name=_('Biography'),
        help_text=_('You can use markdown here.'),
        null=True, blank=True,
    )
    has_arrived = models.BooleanField(
        default=False,
        verbose_name=_('The speaker has arrived'),
    )

    class urls(EventUrls):
        public = '{self.event.urls.base}/speaker/{self.user.code}'
        talks_ical = '{self.urls.public}/talks.ical'

    @cached_property
    def code(self):
        return self.user.code

    @cached_property
    def submissions(self):
        return self.user.submissions.filter(event=self.event)

    @cached_property
    def talks(self):
        from pretalx.submission.models import SubmissionStates
        return self.submissions.filter(state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED])
