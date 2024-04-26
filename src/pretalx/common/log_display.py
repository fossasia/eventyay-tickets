import string

from django.dispatch import receiver
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy as _n

from pretalx.common.models.log import ActivityLog
from pretalx.common.signals import activitylog_display, activitylog_object_link
from pretalx.event.models.event import Event
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.submission.models import (
    Answer,
    AnswerOption,
    CfP,
    Question,
    Submission,
    SubmissionStates,
)

# Usually, we don't have to include the object name in activity log
# strings, because we use ActivityLog.content_object to get the object
# and display it above the message. However, in some cases, like when
# we log the deletion of an object, we don't have the object anymore,
# so we'll want to format the message instead.
TEMPLATE_LOG_NAMES = {
    "pretalx.event.delete": _("The event {name} ({slug}) by {organiser} was deleted."),
    "pretalx.organiser.delete": _("The organiser {name} was deleted."),
}

LOG_NAMES = {
    "pretalx.cfp.update": _("The CfP has been modified."),
    "pretalx.event.create": _("The event has been added."),
    "pretalx.event.update": _("The event was modified."),
    "pretalx.event.activate": _("The event was made public."),
    "pretalx.event.deactivate": _("The event was deactivated."),
    "pretalx.event.plugins.enabled": _("A plugin was enabled."),
    "pretalx.event.plugins.disabled": _("A plugin was disabled."),
    "pretalx.invite.orga.accept": _("The invitation to the event orga was accepted."),
    "pretalx.invite.orga.retract": _("An invitation to the event orga was retracted."),
    "pretalx.invite.orga.send": _("An invitation to the event orga was sent."),
    "pretalx.invite.reviewer.retract": _(
        "The invitation to the review team was retracted."
    ),
    "pretalx.invite.reviewer.send": _("The invitation to the review team was sent."),
    "pretalx.event.invite.orga.accept": _(
        "The invitation to the event orga was accepted."
    ),  # compat
    "pretalx.event.invite.orga.retract": _(
        "An invitation to the event orga was retracted."
    ),  # compat
    "pretalx.event.invite.orga.send": _(
        "An invitation to the event orga was sent."
    ),  # compat
    "pretalx.event.invite.reviewer.retract": _(
        "The invitation to the review team was retracted."
    ),  # compat
    "pretalx.event.invite.reviewer.send": _(
        "The invitation to the review team was sent."
    ),  # compat
    "pretalx.mail.create": _("An email was modified."),
    "pretalx.mail.delete": _("A pending email was deleted."),
    "pretalx.mail.delete_all": _("All pending emails were deleted."),
    "pretalx.mail.sent": _("An email was sent."),
    "pretalx.mail.update": _("An email was modified."),
    "pretalx.mail_template.create": _("A mail template was added."),
    "pretalx.mail_template.delete": _("A mail template was deleted."),
    "pretalx.mail_template.update": _("A mail template was modified."),
    "pretalx.question.create": _("A question was added."),
    "pretalx.question.delete": _("A question was deleted."),
    "pretalx.question.update": _("A question was modified."),
    "pretalx.question.option.create": _("A question option was added."),
    "pretalx.question.option.delete": _("A question option was deleted."),
    "pretalx.question.option.update": _("A question option was modified."),
    "pretalx.tag.create": _("A tag was added."),
    "pretalx.tag.delete": _("A tag was deleted."),
    "pretalx.tag.update": _("A tag was modified."),
    "pretalx.room.create": _("A new room was added."),
    "pretalx.schedule.release": _("A new schedule version was released."),
    "pretalx.submission.accept": _("The proposal was accepted."),
    "pretalx.submission.cancel": _("The proposal was cancelled."),
    "pretalx.submission.confirm": _("The proposal was confirmed."),
    "pretalx.submission.confirmation": _("The proposal was confirmed."),  # Legacy
    "pretalx.submission.create": _("The proposal was added."),
    "pretalx.submission.deleted": _("The proposal was deleted."),
    "pretalx.submission.reject": _("The proposal was rejected."),
    "pretalx.submission.resource.create": _("A proposal resource was added."),
    "pretalx.submission.resource.delete": _("A proposal resource was deleted."),
    "pretalx.submission.resource.update": _("A proposal resource was modified."),
    "pretalx.submission.speakers.add": _("A speaker was added to the proposal."),
    "pretalx.submission.speakers.invite": _("A speaker was invited to the proposal."),
    "pretalx.submission.speakers.remove": _("A speaker was removed from the proposal."),
    "pretalx.submission.unconfirm": _("The proposal was unconfirmed."),
    "pretalx.submission.update": _("The proposal was modified."),
    "pretalx.submission.withdraw": _("The proposal was withdrawn."),
    "pretalx.submission.answer.update": _("A proposal answer was modified."),  # Legacy
    "pretalx.submission.answerupdate": _("A proposal answer was modified."),  # Legacy
    "pretalx.submission.answer.create": _("A proposal answer was added."),  # Legacy
    "pretalx.submission.answercreate": _("A proposal answer was added."),  # Legacy
    "pretalx.submission_type.create": _("A session type was added."),
    "pretalx.submission_type.delete": _("A session type was deleted."),
    "pretalx.submission_type.make_default": _("The session type was made default."),
    "pretalx.submission_type.update": _("A session type was modified."),
    "pretalx.access_code.create": _("An access code was added."),
    "pretalx.access_code.send": _("An access code was sent."),
    "pretalx.access_code.update": _("An access code was modified."),
    "pretalx.access_code.delete": _("An access code was deleted."),
    "pretalx.track.create": _("A track was added."),
    "pretalx.track.delete": _("A track was deleted."),
    "pretalx.track.update": _("A track was modified."),
    "pretalx.speaker.arrived": _("A speaker has been marked as arrived."),
    "pretalx.speaker.unarrived": _("A speaker has been marked as not arrived."),
    "pretalx.user.token.reset": _("The API token was reset."),
    "pretalx.user.password.reset": _("The password was reset."),
    "pretalx.user.password.update": _("The password was modified."),
    "pretalx.user.profile.update": _("The profile was modified."),
}


@receiver(activitylog_display)
def default_activitylog_display(sender: Event, activitylog: ActivityLog, **kwargs):
    if templated_entry := TEMPLATE_LOG_NAMES.get(activitylog.action_type):
        message = str(templated_entry)
        # Check if all placeholders are present in activitylog.data
        placeholders = {v[1] for v in string.Formatter().parse(message) if v[1]}
        if placeholders <= set(activitylog.data.keys()):
            return message.format(**activitylog.data)
    return LOG_NAMES.get(activitylog.action_type)


@receiver(activitylog_object_link)
def default_activitylog_object_link(sender: Event, activitylog: ActivityLog, **kwargs):
    if not activitylog.content_object:
        return
    url = ""
    text = ""
    link_text = ""
    if isinstance(activitylog.content_object, Submission):
        url = activitylog.content_object.orga_urls.base
        link_text = escape(activitylog.content_object.title)
        if activitylog.content_object.state in [
            SubmissionStates.ACCEPTED,
            SubmissionStates.CONFIRMED,
        ]:
            text = _n("Session", "Sessions", 1)
        else:
            text = _n("Proposal", "Proposals", 1)
    if isinstance(activitylog.content_object, Question):
        url = activitylog.content_object.urls.base
        link_text = escape(activitylog.content_object.question)
        text = _("Question")
    if isinstance(activitylog.content_object, AnswerOption):
        url = activitylog.content_object.question.urls.base
        link_text = escape(activitylog.content_object.question.question)
        text = _("Question")
    if isinstance(activitylog.content_object, Answer):
        if activitylog.content_object.submission:
            url = activitylog.content_object.submission.orga_urls.base
        else:
            url = activitylog.content_object.question.urls.base
        link_text = escape(activitylog.content_object.question.question)
        text = _("Answer to question")
    if isinstance(activitylog.content_object, CfP):
        url = activitylog.content_object.urls.text
        link_text = _("CfP")
    if isinstance(activitylog.content_object, MailTemplate):
        url = activitylog.content_object.urls.base
        text = _("Mail template")
        link_text = escape(activitylog.content_object.subject)
    if isinstance(activitylog.content_object, QueuedMail):
        url = activitylog.content_object.urls.base
        text = _("Email")
        link_text = escape(activitylog.content_object.subject)
    if url:
        if not link_text:
            link_text = url
        return f'{text} <a href="{url}">{link_text}</a>'
    if text or link_text:
        return f"{text} {link_text}"
