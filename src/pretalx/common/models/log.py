import json
import logging

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.functional import cached_property
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager


class ActivityLog(models.Model):
    """This model logs actions within an event.

    It is **not** designed to provide a complete or reliable audit
    trail.

    :param is_orga_action: True, if the logged action was performed by a privileged user.
    """

    event = models.ForeignKey(
        to="event.Event",
        on_delete=models.PROTECT,
        related_name="log_entries",
        null=True,
        blank=True,
    )
    person = models.ForeignKey(
        to="person.User",
        on_delete=models.PROTECT,
        related_name="log_entries",
        null=True,
        blank=True,
    )
    content_type = models.ForeignKey(to=ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action_type = models.CharField(max_length=200)
    data = models.TextField(null=True, blank=True)
    is_orga_action = models.BooleanField(default=False)

    objects = ScopedManager(event="event")

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        """Custom __str__ to help with debugging."""
        event = getattr(self.event, "slug", "None")
        person = getattr(self.person, "name", "None")
        return f"ActivityLog(event={event}, person={person}, content_object={self.content_object}, action_type={self.action_type})"

    @cached_property
    def json_data(self):
        if self.data:
            return json.loads(self.data)
        return {}

    @cached_property
    def display(self):
        from pretalx.common.signals import activitylog_display

        for _receiver, response in activitylog_display.send(
            self.event, activitylog=self
        ):
            if response:
                return response

        logger = logging.getLogger(__name__)
        logger.warning(f'Unknown log action "{self.action_type}".')
        return self.action_type

    @cached_property
    def display_object(self) -> str:
        """Returns an organiser backend URL to the object in question (if any)."""
        from pretalx.common.signals import activitylog_object_link
        from pretalx.mail.models import MailTemplate, QueuedMail
        from pretalx.submission.models import (
            Answer,
            AnswerOption,
            CfP,
            Question,
            Submission,
            SubmissionStates,
        )

        url = ""
        text = ""
        link_text = ""
        if isinstance(self.content_object, Submission):
            url = self.content_object.orga_urls.base
            link_text = escape(self.content_object.title)
            if self.content_object.state in [
                SubmissionStates.ACCEPTED,
                SubmissionStates.CONFIRMED,
            ]:
                text = _("Session")
            else:
                text = _("Proposal")
        if isinstance(self.content_object, Question):
            url = self.content_object.urls.base
            link_text = escape(self.content_object.question)
            text = _("Question")
        if isinstance(self.content_object, AnswerOption):
            url = self.content_object.question.urls.base
            link_text = escape(self.content_object.question.question)
            text = _("Question")
        if isinstance(self.content_object, Answer):
            if self.content_object.submission:
                url = self.content_object.submission.orga_urls.base
            else:
                url = self.content_object.question.urls.base
            link_text = escape(self.content_object.question.question)
            text = _("Answer to question")
        if isinstance(self.content_object, CfP):
            url = self.content_object.urls.text
            link_text = _("CfP")
        if isinstance(self.content_object, MailTemplate):
            url = self.content_object.urls.base
            text = _("Mail template")
            link_text = escape(self.content_object.subject)
        if isinstance(self.content_object, QueuedMail):
            url = self.content_object.urls.base
            text = _("Email")
            link_text = escape(self.content_object.subject)
        if url:
            if not link_text:
                link_text = url
            return f'{text} <a href="{url}">{link_text}</a>'
        if text or link_text:
            return f"{text} {link_text}"
        responses = activitylog_object_link.send(sender=self.event, activitylog=self)
        if responses:
            for _receiver, response in responses:
                if response:
                    return response
        return ""
