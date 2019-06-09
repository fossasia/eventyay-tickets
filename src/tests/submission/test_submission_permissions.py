import pytest
from django_scopes import scope

from pretalx.submission.permissions import (
    can_be_canceled, can_be_removed, can_be_reviewed, has_submissions, is_speaker,
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


@pytest.mark.django_db
def test_can_be_reviewed_false():
    assert not can_be_reviewed(None, None)


@pytest.mark.django_db
def test_can_be_reviewed_true(submission):
    with scope(event=submission.event):
        assert can_be_reviewed(None, submission)


@pytest.mark.django_db
def test_submission_permission_can_be_canceled(submission):
    with scope(event=submission.event):
        assert can_be_canceled(None, submission) is False


@pytest.mark.django_db
def test_submission_permission_can_be_removed(submission):
    with scope(event=submission.event):
        assert can_be_removed(None, submission) is False
