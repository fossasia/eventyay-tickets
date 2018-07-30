import rules

from pretalx.person.permissions import can_change_submissions, is_reviewer
from pretalx.submission.models import SubmissionStates


@rules.predicate
def has_submissions(user, obj):
    event = obj.event
    return event.submissions.filter(speakers__in=[user]).exists()


@rules.predicate
def is_speaker(user, obj):
    if hasattr(obj, 'submission'):
        obj = obj.submission
    return obj and user in obj.speakers.all()


@rules.predicate
def can_be_withdrawn(user, obj):
    return obj and SubmissionStates.WITHDRAWN in SubmissionStates.valid_next_states.get(
        obj.state, []
    )


@rules.predicate
def can_be_rejected(user, obj):
    return obj and SubmissionStates.REJECTED in SubmissionStates.valid_next_states.get(
        obj.state, []
    )


@rules.predicate
def can_be_accepted(user, obj):
    return obj and SubmissionStates.ACCEPTED in SubmissionStates.valid_next_states.get(
        obj.state, []
    )


@rules.predicate
def can_be_confirmed(user, obj):
    return obj and SubmissionStates.CONFIRMED in SubmissionStates.valid_next_states.get(
        obj.state, []
    )


@rules.predicate
def can_be_canceled(user, obj):
    return obj and SubmissionStates.CANCELED in SubmissionStates.valid_next_states.get(
        obj.state, []
    )


@rules.predicate
def can_be_removed(user, obj):
    return obj and SubmissionStates.DELETED in SubmissionStates.valid_next_states.get(
        obj.state, []
    )


@rules.predicate
def can_be_edited(user, obj):
    return obj and obj.editable


@rules.predicate
def is_review_author(user, obj):
    return obj and obj.user == user


@rules.predicate
def can_be_reviewed(user, obj):
    from django.utils.timezone import now

    if not obj:
        return False
    if hasattr(obj, 'submission'):
        obj = obj.submission
    deadline = obj.event.settings.review_deadline
    state = obj.state == SubmissionStates.SUBMITTED
    time = True if not deadline else now() <= deadline
    return state and time


rules.add_perm('submission.withdraw_submission', can_be_withdrawn & is_speaker)
rules.add_perm('submission.reject_submission', can_be_rejected & can_change_submissions)
rules.add_perm('submission.accept_submission', can_be_accepted & can_change_submissions)
rules.add_perm(
    'submission.confirm_submission',
    can_be_confirmed & (is_speaker | can_change_submissions),
)
rules.add_perm(
    'submission.cancel_submission',
    can_be_canceled & (is_speaker | can_change_submissions),
)
rules.add_perm('submission.remove_submission', can_be_removed & can_change_submissions)
rules.add_perm(
    'submission.edit_submission', (can_be_edited & is_speaker) | can_change_submissions
)
rules.add_perm(
    'submission.view_submission', is_speaker | can_change_submissions | is_reviewer
)
rules.add_perm('submission.review_submission', is_reviewer & can_be_reviewed)
rules.add_perm('submission.edit_review', can_be_reviewed & is_review_author)
rules.add_perm('submission.view_reviews', is_reviewer & ~is_speaker)
rules.add_perm('submission.edit_speaker_list', is_speaker | can_change_submissions)
rules.add_perm(
    'submission.view_feedback', is_speaker | can_change_submissions | is_reviewer
)
