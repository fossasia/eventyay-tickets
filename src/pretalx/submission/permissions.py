import rules

from pretalx.person.permissions import is_orga, is_reviewer
from pretalx.submission.models import SubmissionStates


@rules.predicate
def has_submissions(user, obj):
    event = obj.event
    return event.submissions.filter(speakers__in=[user]).exists()


@rules.predicate
def is_speaker(user, obj):
    if obj is None:
        return False
    if hasattr(obj, 'submission'):
        obj = obj.submission
    return user in obj.speakers.all()


@rules.predicate
def can_be_withdrawn(user, obj):
    if obj is None:
        return False
    return SubmissionStates.WITHDRAWN in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_rejected(user, obj):
    if obj is None:
        return False
    return SubmissionStates.REJECTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_accepted(user, obj):
    if obj is None:
        return False
    return SubmissionStates.ACCEPTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_confirmed(user, obj):
    if obj is None:
        return False
    return SubmissionStates.CONFIRMED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_canceled(user, obj):
    if obj is None:
        return False
    return SubmissionStates.CANCELED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_removed(user, obj):
    if obj is None:
        return False
    return SubmissionStates.DELETED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_edited(user, obj):
    if obj is None:
        return False
    return obj.editable


@rules.predicate
def is_review_author(user, obj):
    if obj is None:
        return False
    return obj.user == user


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
rules.add_perm('submission.reject_submission', can_be_rejected & is_orga)
rules.add_perm('submission.accept_submission', can_be_accepted & is_orga)
rules.add_perm('submission.confirm_submission', can_be_confirmed & (is_speaker | is_orga))
rules.add_perm('submission.cancel_submission', can_be_canceled & (is_speaker | is_orga))
rules.add_perm('submission.remove_submission', can_be_removed & is_orga)
rules.add_perm('submission.edit_submission', (can_be_edited & is_speaker) | is_orga)
rules.add_perm('submission.view_submission', is_speaker | is_orga | is_reviewer)
rules.add_perm('submission.review_submission', is_reviewer & ~is_speaker & can_be_reviewed)
rules.add_perm('submission.edit_review', can_be_reviewed & is_review_author)
rules.add_perm('submission.view_reviews', is_reviewer & ~is_speaker)
rules.add_perm('submission.edit_speaker_list', is_speaker | is_orga)
rules.add_perm('submission.view_feedback', is_speaker | is_orga | is_reviewer)
