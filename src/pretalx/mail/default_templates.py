from django.utils.translation import ugettext_lazy as _


GENERIC_SUBJECT = _('Your submission: {submission_title}')


ACK_TEXT = _('''Hi!

We have received your submission "{submission_title}" to
{event_name}. We will notify you once we have had time to consider all
submissions, but until then you can see and edit your submission at
{submission_url}.

Please do not hesitate to contact us if you have any questions!

The {event_name} orga''')


ACCEPT_TEXT = _('''Hi!

We are happy to tell you that we accept your submission "{submission_title}"
to {event_name}. Please click this link to confirm your attendance:

    {confirmation_link}

We look forward to seeing you at {event} - Please contact us if you have any
questions! We will reach out again before the conference to tell you details
about your slot in the schedule and technical details concerning the room
and presentation tech.

See you there!
The {event_name} orga''')


REJECT_TEXT = _('''Hi!

We are sorry to tell you that we cannot accept your submission
"{submission_title}" to {event_name}. There were just too many great
submissions - we hope to see you at {event_name} as an attendee instead
of a speaker!

The {event_name} orga''')
