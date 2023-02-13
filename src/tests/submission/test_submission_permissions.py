import pytest
from django_scopes import scope

from pretalx.submission.models import Submission, SubmissionStates
from pretalx.submission.permissions import (
    can_be_accepted,
    can_be_canceled,
    can_be_confirmed,
    can_be_rejected,
    can_be_removed,
    can_be_reviewed,
    can_be_withdrawn,
    can_view_all_reviews,
    can_view_reviews,
    has_reviewer_access,
    has_submissions,
    is_speaker,
)


@pytest.mark.django_db
def test_has_submission_true(event, submission, speaker):
    with scope(event=event):
        assert has_submissions(speaker, submission)


@pytest.mark.django_db
def test_has_submission_false(event, submission, orga_user):
    with scope(event=event):
        assert not has_submissions(orga_user, submission)


@pytest.mark.django_db
def test_is_speaker_true(event, slot, speaker):
    with scope(event=event):
        assert is_speaker(speaker, slot.submission)
        assert is_speaker(speaker, slot)


@pytest.mark.django_db
def test_is_speaker_false(event, submission, orga_user):
    with scope(event=event):
        assert not is_speaker(orga_user, submission)


@pytest.mark.parametrize(
    "current_state",
    (
        "submitted",
        "accepted",
        "rejected",
        "confirmed",
        "canceled",
        "withdrawn",
        "deleted",
    ),
)
@pytest.mark.parametrize(
    "target_state",
    (
        "accepted",
        "rejected",
        "confirmed",
        "canceled",
        "withdrawn",
        "deleted",
    ),
)
def test_can_change_state(current_state, target_state):
    submission = Submission(state=current_state)
    permissions = {
        "accepted": can_be_accepted,
        "rejected": can_be_rejected,
        "confirmed": can_be_confirmed,
        "canceled": can_be_canceled,
        "withdrawn": can_be_withdrawn,
        "deleted": can_be_removed,
    }
    assert permissions[target_state](None, submission) is (
        target_state in SubmissionStates.valid_next_states[current_state]
    )


def test_reviewer_permission_degrades_gracefully():
    with pytest.raises(Exception):  # noqa
        has_reviewer_access(None, None)


@pytest.mark.django_db
def test_without_review_phases(event):
    with scope(event=event):
        event.review_phases.all().update(is_active=False)
        assert can_view_all_reviews(None, event) is False
        assert can_view_reviews(None, event) is False


@pytest.mark.django_db
@pytest.mark.parametrize("value,expected", (("always", True), ("never", False)))
def test_can_view_reviews(event, value, expected):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_see_other_reviews = value
        phase.save()
        assert can_view_reviews(None, event) is expected


def test_can_be_reviewed_false():
    assert not can_be_reviewed(None, None)


@pytest.mark.django_db
def test_can_be_reviewed_true(submission):
    with scope(event=submission.event):
        assert can_be_reviewed(None, submission)
