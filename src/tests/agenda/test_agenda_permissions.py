import pytest
from django_scopes import scope

from pretalx.agenda.permissions import (
    is_agenda_visible, is_feedback_ready, is_speaker_viewable,
)


@pytest.mark.django_db
@pytest.mark.parametrize('is_public,show_schedule,has_schedule,result', (
    (True, True, True, True),
    (True, True, False, False),
    (True, False, True, False),
    (False, True, True, False),
    (False, False, True, False),
))
def test_agenda_permission_is_agenda_visible(is_public, show_schedule, has_schedule, result, event):
    with scope(event=event):
        event.is_public = is_public
        event.settings.show_schedule = show_schedule
        if has_schedule:
            event.release_schedule('42')
        assert is_agenda_visible(None, event) is result


@pytest.mark.django_db
@pytest.mark.parametrize('slot_visible,accept_feedback,result', (
    (True, True, True),
    (True, False, False),
    (False, True, False),
    (False, False, False),
))
def test_agenda_permission_is_feedback_ready(slot_visible, accept_feedback, result, slot, monkeypatch):
    monkeypatch.setattr('pretalx.agenda.permissions.is_submission_visible', lambda x, y: slot_visible)
    monkeypatch.setattr('pretalx.submission.models.submission.Submission.does_accept_feedback', accept_feedback)
    assert is_feedback_ready(None, slot.submission) is result


@pytest.mark.django_db
@pytest.mark.parametrize('agenda_visible,result', (
    (True, True),
    (False, False),
))
def test_agenda_permission_is_speaker_viewable(agenda_visible, result, speaker, slot, schedule, monkeypatch):
    monkeypatch.setattr('pretalx.agenda.permissions.is_agenda_visible', lambda x, y: agenda_visible)
    with scope(event=schedule.event):
        assert is_speaker_viewable(None, speaker.profiles.first()) is result
