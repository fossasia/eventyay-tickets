from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from pretalx.common.mixins import LogMixin
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls


class SpeakerProfile(LogMixin, models.Model):
    """All :class:`~pretalx.event.models.event.Event` related data concerning a :class:`~pretalx.person.models.user.User` is stored here.

    :param has_arrived: Can be set to track speaker arrival. Will be used in
        warnings about missing speakers.
    """
    user = models.ForeignKey(
        to='person.User',
        related_name='profiles',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    event = models.ForeignKey(
        to='event.Event', related_name='+', on_delete=models.CASCADE
    )
    biography = models.TextField(
        verbose_name=_('Biography'),
        help_text=phrases.base.use_markdown,
        null=True,
        blank=True,
    )
    has_arrived = models.BooleanField(
        default=False, verbose_name=_('The speaker has arrived')
    )

    class urls(EventUrls):
        public = '{self.event.urls.base}speaker/{self.user.code}/'
        talks_ical = '{self.urls.public}talks.ics'

    class orga_urls(EventUrls):
        base = '{self.event.orga_urls.speakers}{self.user.id}/'
        password_reset = '{self.event.orga_urls.speakers}{self.user.id}/reset'
        toggle_arrived = '{self.event.orga_urls.speakers}{self.user.id}/toggle-arrived'

    def __str__(self):
        """Help when debugging."""
        user = self.user.get_display_name() if self.user else None
        return f'SpeakerProfile(event={self.event.slug}, user={user})'

    @cached_property
    def code(self):
        return self.user.code

    @cached_property
    def submissions(self):
        """All non-deleted :class:`~pretalx.submission.models.submission.Submission` objects by this user on this event."""
        return self.user.submissions.filter(event=self.event)

    @cached_property
    def talks(self):
        """A queryset of :class:`~pretalx.submission.models.submission.Submission` objects.

        Contains all visible talks by this user on this event."""
        return self.event.talks.filter(speakers__in=[self.user])

    @cached_property
    def answers(self):
        """A queryset of :class:`~pretalx.submission.models.question.Answer` objects.

        Includes all answers the user has given either for themselves or for
        their talks for this event."""
        from pretalx.submission.models import Answer, Submission

        submissions = Submission.objects.filter(
            event=self.event, speakers__in=[self.user]
        )
        return Answer.objects.filter(
            models.Q(submission__in=submissions) | models.Q(person=self.user)
        )
