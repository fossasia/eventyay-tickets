import rules

from pretalx.person.permissions import is_orga, is_reviewer
from pretalx.submission.models import SubmissionStates


@rules.predicate
def is_speaker(user, obj):
    return user in obj.speakers.all()


@rules.predicate
def can_be_withdrawn(user, obj):
    return SubmissionStates.WITHDRAWN in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_rejected(user, obj):
    return SubmissionStates.REJECTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_accepted(user, obj):
    return SubmissionStates.ACCEPTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_confirmed(user, obj):
    return SubmissionStates.CONFIRMED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_canceled(user, obj):
    return SubmissionStates.CANCELED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_removed(user, obj):
    return SubmissionStates.DELETED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_unconfirmed(user, obj):
    return SubmissionStates.ACCEPTED in SubmissionStates.valid_next_states.get(obj.state, []) and obj.state == SubmissionStates.CONFIRMED


@rules.predicate
def can_be_edited(user, obj):
    return obj.editable


@rules.predicate
def is_review_author(user, obj):
    return obj.user == user


rules.add_perm('submission.withdraw_submission', can_be_withdrawn & is_speaker)
rules.add_perm('submission.reject_submission', can_be_rejected & is_orga)
rules.add_perm('submission.accept_submission', can_be_accepted & is_orga)
rules.add_perm('submission.confirm_submission', can_be_confirmed & (is_speaker | is_orga))
rules.add_perm('submission.cancel_submission', can_be_canceled & (is_speaker | is_orga))
rules.add_perm('submission.unconfirm_submission', can_be_unconfirmed & (is_speaker | is_orga))
rules.add_perm('submission.remove_submission', can_be_removed & is_orga)
rules.add_perm('submission.edit_submission', (can_be_edited & is_speaker) | is_orga)
rules.add_perm('submission.review_submission', is_reviewer & ~is_speaker)
rules.add_perm('submission.view_submission', is_speaker | is_orga | is_reviewer)
rules.add_perm('submission.edit_speaker_list', is_speaker | is_orga)
rules.add_perm('submission.view_feedback', is_speaker | is_orga | is_reviewer)
