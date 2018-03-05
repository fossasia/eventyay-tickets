from django.utils.translation import ugettext_noop as _
from i18nfield.strings import LazyI18nString

GENERIC_SUBJECT = LazyI18nString.from_gettext(_('Your submission: {submission_title}'))

ACK_TEXT = LazyI18nString.from_gettext(_('''Hi!

We have received your submission "{submission_title}" to
{event_name}. We will notify you once we have had time to consider all
submissions, but until then you can see and edit your submission at
{submission_url}.

Please do not hesitate to contact us if you have any questions!

The {event_name} organisers'''))

ACCEPT_TEXT = LazyI18nString.from_gettext(_('''Hi!

We are happy to tell you that we accept your submission "{submission_title}"
to {event_name}. Please click this link to confirm your attendance:

    {confirmation_link}

We look forward to seeing you at {event_name} - Please contact us if you have any
questions! We will reach out again before the conference to tell you details
about your slot in the schedule and technical details concerning the room
and presentation tech.

See you there!
The {event_name} organisers'''))

REJECT_TEXT = LazyI18nString.from_gettext(_('''Hi!

We are sorry to tell you that we cannot accept your submission
"{submission_title}" to {event_name}. There were just too many great
submissions - we hope to see you at {event_name} as an attendee instead
of a speaker!

The {event_name} organisers'''))

UPDATE_TEXT = LazyI18nString.from_gettext(_('''Hi!

We have released a new schedule version, and your talk slot has moved:
From {old_datetime} ({old_room}) to {new_datetime} ({new_room}).

If this poses a problem, don't hesitate to contact us!

The {event_name} organisers'''))

QUESTION_SUBJECT = LazyI18nString.from_gettext(_('We have some questions about your submission'))
QUESTION_TEXT = LazyI18nString.from_gettext(_('''Hi!

We have some open questions about yourself and your submission that we'd
like to ask you to answer:

{questions}

You can answer them at {url}.

Please do not hesitate to contact us if you have any questions in turn!

The {event_name} orga'''))
