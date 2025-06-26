from django.utils.translation import gettext_noop as _
from i18nfield.strings import LazyI18nString

GENERIC_SUBJECT = LazyI18nString.from_gettext(_("Your proposal: {submission_title}"))

ACK_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

We have received your proposal “{submission_title}” to
{event_name}. We will notify you once we have had time to consider all
proposals, but until then you can see and edit your proposal at
{submission_url}.

Please do not hesitate to contact us if you have any questions!

The {event_name} organisers"""
    )
)

ACCEPT_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

We are happy to tell you that we accept your proposal “{submission_title}”
to {event_name}. Please click this link to confirm your attendance:

    {confirmation_link}

We look forward to seeing you at {event_name} - Please contact us if you have any
questions! We will reach out again before the conference to tell you details
about your slot in the schedule and technical details concerning the room
and presentation tech.

See you there!
The {event_name} organisers"""
    )
)

REJECT_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

We are sorry to tell you that we cannot accept your proposal
“{submission_title}” to {event_name}. There were just too many great
proposals - we hope to see you at {event_name} as an attendee instead
of a speaker!

The {event_name} organisers"""
    )
)

UPDATE_SUBJECT = LazyI18nString.from_gettext(_("New schedule!"))
UPDATE_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

We have released a new schedule version, and wanted to tell you:

{speaker_schedule_new}

We look forward to seeing you, and please contact us if there is any problem with your session or assigned slot.

The {event_name} organisers"""
    )
)

QUESTION_SUBJECT = LazyI18nString.from_gettext(
    _("We have some questions about your proposal")
)
QUESTION_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

We have some open questions about yourself and your proposal that we’d
like to ask you to answer:

{questions}

You can answer them at {url}.

Please do not hesitate to contact us if you have any questions in turn!

The {event_name} organisers"""
    )
)

NEW_SUBMISSION_SUBJECT = LazyI18nString.from_gettext(
    _("New proposal: {proposal_title}")
)
NEW_SUBMISSION_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi,

you have received a new proposal for your event {event_name}:
“{submission_title}” by {speakers}.
You can see details at

  {orga_url}

All the best,
your {event_name} CfP system.
"""
    )
)

SPEAKER_INVITE_SUBJECT = LazyI18nString.from_gettext(
    _("You have been added to a proposal for {event_name}")
)

NEW_SPEAKER_INVITE_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

You have been added to a proposal of {event_name}, titled “{proposal_title}”.
An account has been created for you – please follow this link to set your account password.

{invitation_link}

Afterwards, you can edit your user profile and see the state of your proposal.

The {event} orga crew"""
    )
)
EXISTING_SPEAKER_INVITE_TEXT = LazyI18nString.from_gettext(
    _(
        """Hi!

You have been added to a proposal of {event_name}, titled “{proposal_title}”.
Please follow this link to edit your user profile and see the state of your proposal:

{proposal_url}

The {event_name} organisers"""
    )
)


def get_default_template(role):
    from pretalx.mail.models import MailTemplateRoles

    TEMPLATE_MAPPING = {
        MailTemplateRoles.SUBMISSION_ACCEPT: (GENERIC_SUBJECT, ACCEPT_TEXT),
        MailTemplateRoles.SUBMISSION_REJECT: (GENERIC_SUBJECT, REJECT_TEXT),
        MailTemplateRoles.NEW_SUBMISSION: (GENERIC_SUBJECT, ACK_TEXT),
        MailTemplateRoles.NEW_SUBMISSION_INTERNAL: (
            NEW_SUBMISSION_SUBJECT,
            NEW_SUBMISSION_TEXT,
        ),
        MailTemplateRoles.NEW_SCHEDULE: (UPDATE_SUBJECT, UPDATE_TEXT),
        MailTemplateRoles.QUESTION_REMINDER: (QUESTION_SUBJECT, QUESTION_TEXT),
        MailTemplateRoles.NEW_SPEAKER_INVITE: (
            SPEAKER_INVITE_SUBJECT,
            NEW_SPEAKER_INVITE_TEXT,
        ),
        MailTemplateRoles.EXISTING_SPEAKER_INVITE: (
            SPEAKER_INVITE_SUBJECT,
            EXISTING_SPEAKER_INVITE_TEXT,
        ),
    }
    return TEMPLATE_MAPPING[role]
