import rules

from pretalx.person.permissions import can_change_submissions, is_reviewer
from pretalx.submission.models import SubmissionStates
from pretalx.submission.permissions import can_be_edited


@rules.predicate
def is_event_visible(user, event):
    return event and event.is_public


@rules.predicate
def can_request_speakers(user, submission):
    # Only allow to request speakers if the field is active in the CfP
    return (
        submission.state != SubmissionStates.DRAFT
        and submission.event.cfp.request_additional_speaker
    )


rules.add_perm(
    "cfp.view_event", is_event_visible | (can_change_submissions | is_reviewer)
)
rules.add_perm("cfp.add_speakers", can_be_edited & can_request_speakers)
