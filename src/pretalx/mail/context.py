from django.dispatch import receiver
from django.template.defaultfilters import date as _date
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from pretalx.mail.placeholders import SimpleFunctionalMailTextPlaceholder
from pretalx.mail.signals import register_mail_placeholders


def get_mail_context(**kwargs):
    event = kwargs["event"]
    if "submission" in kwargs and "slot" not in kwargs:
        slot = kwargs["submission"].slot
        if slot and slot.start and slot.room:
            kwargs["slot"] = kwargs["submission"].slot
    context = {}
    for recv, placeholders in register_mail_placeholders.send(sender=event):
        if not isinstance(placeholders, (list, tuple)):
            placeholders = [placeholders]
        for placeholder in placeholders:
            if all(required in kwargs for required in placeholder.required_context):
                context[placeholder.identifier] = placeholder.render(kwargs)
    return context


def get_available_placeholders(event, kwargs):
    params = {}
    for recv, placeholders in register_mail_placeholders.send(sender=event):
        if not isinstance(placeholders, (list, tuple)):
            placeholders = [placeholders]
        for placeholder in placeholders:
            if all(required in kwargs for required in placeholder.required_context):
                params[placeholder.identifier] = placeholder
    return params


@receiver(register_mail_placeholders, dispatch_uid="pretalx_register_base_placeholders")
def base_placeholders(sender, **kwargs):

    placeholders = [
        SimpleFunctionalMailTextPlaceholder(
            "event",
            ["event"],
            lambda event: event.name,
            lambda event: event.name,
            _("The event's full name"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "event_name",
            ["event"],
            lambda event: event.name,
            lambda event: event.name,
            _("The event's full name"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "event_slug",
            ["event"],
            lambda event: event.slug,
            lambda event: event.slug,
            _("The event's short form, used in URLs"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "event_url",
            ["event"],
            lambda event: event.urls.base.full(),
            lambda event: f"https://pretalx.com/{event.slug}/",
            _("The event's public base URL"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "event_schedule_url",
            ["event"],
            lambda event: event.urls.schedule.full(),
            lambda event: f"https://pretalx.com/{event.slug}/schedule/",
            _("The event's public schedule URL"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "event_cfp_url",
            ["event"],
            lambda event: event.cfp.urls.base.full(),
            lambda event: f"https://pretalx.com/{event.slug}/cfp",
            _("The event's public CfP URL"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "all_submissions_url",
            ["event", "user"],
            lambda event, user: event.urls.user_submissions.full(),
            "https://pretalx.example.com/democon/me/submissions/",
            _("URL to a user's list of proposals"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "deadline",
            ["event"],
            lambda event: _date(
                event.cfp.deadline.astimezone(event.tz), "SHORT_DATETIME_FORMAT"
            )
            if event.cfp.deadline
            else "",
            lambda event: _date(
                event.cfp.deadline.astimezone(event.tz), "SHORT_DATETIME_FORMAT"
            )
            if event.cfp.deadline
            else "",
            _("The general CfP deadline"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "code",
            ["submission"],
            lambda submission: submission.code,
            "F8VVL",
            _("The proposal's unique ID"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "talk_url",
            ["slot"],
            lambda slot: slot.submission.urls.public.full(),
            "https://pretalx.example.com/democon/schedule/F8VVL/",
            _("The proposal's public URL"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "edit_url",
            ["submission"],
            lambda submission: submission.urls.user_base.full(),
            "https://pretalx.example.com/democon/me/submissions/F8VVL/",
            _("The speaker's edit page for the proposal"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "submission_url",
            ["submission"],
            lambda submission: submission.urls.user_base.full(),
            "https://pretalx.example.com/democon/me/submissions/F8VVL/",
            _("The speaker's edit page for the proposal"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "confirmation_link",
            ["submission"],
            lambda submission: submission.urls.confirm.full(),
            "https://pretalx.example.com/democon/me/submissions/F8VVL/confirm",
            _("Link to confirm a proposal after it has been accepted."),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "withdraw_link",
            ["submission"],
            lambda submission: submission.urls.withdraw.full(),
            "https://pretalx.example.com/democon/me/submissions/F8VVL/withdraw",
            _("Link to withdraw the proposal"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "proposal_title",
            ["submission"],
            lambda submission: submission.title,
            "Open-architected uniform middleware",
            _("The proposal's title"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "submission_title",
            ["submission"],
            lambda submission: submission.title,
            "Open-architected uniform middleware",
            _("The proposal's title"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "speakers",
            ["submission"],
            lambda submission: submission.display_speaker_names,
            "Open-architected uniform middleware",
            _("The name(s) of all speakers in this proposal."),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "session_type",
            ["submission"],
            lambda submission: str(submission.submission_type.name),
            "Workshop",
            _("The proposal's session type"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "submission_type",
            ["submission"],
            lambda submission: str(submission.submission_type.name),
            "Workshop",
            _("The proposal's session type"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "track_name",
            ["submission"],
            lambda submission: str(submission.track.name) if submission.track else "",
            "Science",
            _("The track the proposal belongs to"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "session_start_date",
            ["slot"],
            lambda slot: _date(slot.start, "SHORT_DATE_FORMAT"),
            _date(now(), "SHORT_DATE_FORMAT"),
            _("The session's start date"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "session_start_time",
            ["slot"],
            lambda slot: _date(slot.start, "TIME_FORMAT"),
            _date(now(), "TIME_FORMAT"),
            _("The session's start time"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "session_end_date",
            ["slot"],
            lambda slot: _date(slot.real_end, "SHORT_DATE_FORMAT"),
            _date(now(), "SHORT_DATE_FORMAT"),
            _("The session's end date"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "session_end_time",
            ["slot"],
            lambda slot: _date(slot.real_end, "TIME_FORMAT"),
            _date(now(), "TIME_FORMAT"),
            _("The session's end time"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "session_room",
            ["slot"],
            lambda slot: str(slot.room),
            _("Room 101"),
            _("The session's room"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "name",
            ["user"],
            lambda user: user.name,
            _("Jane Doe"),
            _("The addressed user's full name"),
        ),
        SimpleFunctionalMailTextPlaceholder(
            "email",
            ["user"],
            lambda user: user.email,
            "jane@example.org",
            _("The addressed user's email address"),
        ),
    ]

    return placeholders
