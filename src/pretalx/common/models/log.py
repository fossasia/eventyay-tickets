import logging

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django_scopes import ScopedManager

from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.submission.models import Answer, AnswerOption, CfP, Question, Submission


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

    def display(self):
        from pretalx.common.signals import activitylog_display

        for receiver, response in activitylog_display.send(
            self.event, activitylog=self
        ):
            if response:
                return response

        logger = logging.getLogger(__name__)
        logger.warning(f'Unknown log action "{self.action_type}".')
        return self.action_type

    def get_public_url(self) -> str:
        """Returns a public URL to the object in question (if any)."""
        if isinstance(self.content_object, Submission):
            return self.content_object.urls.public
        if isinstance(self.content_object, CfP):
            return self.content_object.urls.public
        return ""

    def get_orga_url(self) -> str:
        """Returns an organiser backend URL to the object in question (if
        any)."""
        if isinstance(self.content_object, Submission):
            return self.content_object.orga_urls.base
        if isinstance(self.content_object, Question):
            return self.content_object.urls.base
        if isinstance(self.content_object, AnswerOption):
            return self.content_object.question.urls.base
        if isinstance(self.content_object, Answer):
            if self.content_object.submission:
                return self.content_object.submission.orga_urls.base
            return self.content_object.question.urls.base
        if isinstance(self.content_object, CfP):
            return self.content_object.urls.text
        if isinstance(self.content_object, (MailTemplate, QueuedMail)):
            return self.content_object.urls.base
        return ""
