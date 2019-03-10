import rules
from django.utils.timezone import now

from pretalx.person.permissions import can_change_submissions, is_reviewer


@rules.predicate
def is_event_visible(user, event):
    return event and event.is_public


@rules.predicate
def submission_deadline_open(user, submission):
    deadline = submission.submission_type.deadline or submission.event.cfp.deadline
    return (not deadline) or now() <= deadline


rules.add_perm('cfp.view_event', is_event_visible | (can_change_submissions | is_reviewer))
rules.add_perm('cfp.add_speakers', submission_deadline_open)
