from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from pretalx.agenda.rules import can_view_schedule, is_speaker_viewable
from pretalx.common.models.mixins import PretalxModel
from pretalx.common.text.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.orga.rules import can_view_speaker_names
from pretalx.person.rules import (
    can_mark_speakers_arrived,
    is_administrator,
    is_reviewer,
)
from pretalx.submission.rules import orga_can_change_submissions


class SpeakerProfile(PretalxModel):
    """All :class:`~pretalx.event.models.event.Event` related data concerning
    a.

    :class:`~pretalx.person.models.user.User` is stored here.

    :param has_arrived: Can be set to track speaker arrival. Will be used in
        warnings about missing speakers.
    """

    user = models.ForeignKey(
        to="person.User",
        related_name="profiles",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    event = models.ForeignKey(
        to="event.Event", related_name="+", on_delete=models.CASCADE
    )
    biography = models.TextField(
        verbose_name=_("Biography"),
        help_text=phrases.base.use_markdown,
        null=True,
        blank=True,
    )
    has_arrived = models.BooleanField(
        default=False, verbose_name=_("The speaker has arrived")
    )

    log_prefix = "pretalx.user.profile"

    class Meta:
        # These permissions largely apply to event-scoped user actions
        rules_permissions = {
            "list": can_view_schedule | (is_reviewer & can_view_speaker_names),
            "reviewer_list": is_reviewer & can_view_speaker_names,
            "orga_list": orga_can_change_submissions
            | (is_reviewer & can_view_speaker_names),
            "view": is_speaker_viewable
            | orga_can_change_submissions
            | (is_reviewer & can_view_speaker_names),
            "orga_view": orga_can_change_submissions
            | (is_reviewer & can_view_speaker_names),
            "create": is_administrator,
            "update": orga_can_change_submissions,
            "mark_arrived": orga_can_change_submissions & can_mark_speakers_arrived,
            "delete": is_administrator,
        }

    class urls(EventUrls):
        public = "{self.event.urls.base}speaker/{self.user.code}/"
        social_image = "{public}og-image"
        talks_ical = "{self.urls.public}talks.ics"

    class orga_urls(EventUrls):
        base = "{self.event.orga_urls.speakers}{self.user.code}/"
        password_reset = "{self.event.orga_urls.speakers}{self.user.code}/reset"
        toggle_arrived = (
            "{self.event.orga_urls.speakers}{self.user.code}/toggle-arrived"
        )

    def __str__(self):
        """Help when debugging."""
        user = self.user.get_display_name() if self.user else None
        return f"SpeakerProfile(event={self.event.slug}, user={user})"

    @cached_property
    def code(self):
        return self.user.code

    @cached_property
    def submissions(self):
        """All non-deleted.

        :class:`~pretalx.submission.models.submission.Submission` objects by
        this user on this event.
        """
        return self.user.submissions.filter(event=self.event)

    @cached_property
    def talks(self):
        """A queryset of.

        :class:`~pretalx.submission.models.submission.Submission` objects.

        Contains all visible talks by this user on this event.
        """
        return self.event.talks.filter(speakers__in=[self.user])

    @cached_property
    def answers(self):
        """A queryset of :class:`~pretalx.submission.models.question.Answer`
        objects.

        Includes all answers the user has given either for themselves or
        for their talks for this event.
        """
        from pretalx.submission.models import Answer, Submission

        submissions = Submission.objects.filter(
            event=self.event, speakers__in=[self.user]
        )
        return Answer.objects.filter(
            models.Q(submission__in=submissions) | models.Q(person=self.user)
        ).order_by("question__position")

    @property
    def reviewer_answers(self):
        return self.answers.filter(question__is_visible_to_reviewers=True).order_by(
            "question__position"
        )

    @cached_property
    def avatar(self):
        if self.event.cfp.request_avatar:
            return self.user.avatar

    @cached_property
    def avatar_url(self):
        if self.event.cfp.request_avatar:
            return self.user.get_avatar_url(event=self.event)
