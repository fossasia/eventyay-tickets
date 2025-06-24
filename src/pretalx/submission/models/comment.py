from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from pretalx.common.models.mixins import PretalxModel
from pretalx.common.text.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.submission.rules import (
    has_reviewer_access,
    is_comment_author,
    orga_can_change_submissions,
    submission_comments_active,
)


class SubmissionComment(PretalxModel):
    """Comments allow reviewers and organizers to discuss submissions.

    They are separate from reviews and provide a forum-style discussion space.
    """

    submission = models.ForeignKey(
        to="submission.Submission", related_name="comments", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        to="person.User", related_name="submission_comments", on_delete=models.CASCADE
    )
    text = models.TextField(
        verbose_name=_("Comment"),
        help_text=phrases.base.use_markdown,
    )
    reply_to = models.ForeignKey(
        to="submission.SubmissionComment",
        related_name="replies",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    objects = ScopedManager(event="submission__event")

    class Meta:
        ordering = ("created",)
        rules_permissions = {
            "view": submission_comments_active
            & (has_reviewer_access | orga_can_change_submissions),
            "create": submission_comments_active
            & (has_reviewer_access | orga_can_change_submissions),
            "delete": submission_comments_active
            & (has_reviewer_access | orga_can_change_submissions)
            & is_comment_author,
        }

    def __str__(self):
        return f'Comment by {self.user.get_display_name()} on "{self.submission.title}"'

    @cached_property
    def event(self):
        return self.submission.event

    class urls(EventUrls):
        _base = "{self.submission.orga_urls.comments}{self.pk}/"
        delete = "{_base}delete"
