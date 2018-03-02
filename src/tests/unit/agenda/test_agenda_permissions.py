import pytest

from pretalx.agenda.permissions import (
    is_agenda_visible, is_feedback_ready, is_slot_visible, is_speaker_viewable,
)


@pytest.mark.django_db
@pytest.mark.parametrize('is_public,show_schedule,result', (
    (True, True, True),
    (True, False, False),
    (False, True, False),
    (False, False, False),
))
def test_agenda_permission_is_agenda_visible(is_public, show_schedule, result, event):
    event.is_public = is_public
    event.settings.show_schedule = show_schedule
    assert is_agenda_visible(None, event) is result


@pytest.mark.django_db
@pytest.mark.parametrize('agenda_visible,slot_visible,result', (
    (True, True, True),
    (True, False, False),
    (False, True, False),
    (False, False, False),
))
def test_agenda_permission_is_slot_visible(agenda_visible, slot_visible, result, slot, monkeypatch):
    monkeypatch.setattr('pretalx.agenda.permissions.is_agenda_visible', lambda x, y: agenda_visible)
    slot.is_visible = slot_visible
    assert is_slot_visible(None, slot) is result


@pytest.mark.django_db
@pytest.mark.parametrize('slot_visible,accept_feedback,result', (
    (True, True, True),
    (True, False, False),
    (False, True, False),
    (False, False, False),
))
def test_agenda_permission_is_feedback_ready(slot_visible, accept_feedback, result, slot, monkeypatch):
    monkeypatch.setattr('pretalx.agenda.permissions.is_slot_visible', lambda x, y: slot_visible)
    monkeypatch.setattr('pretalx.submission.models.submission.Submission.does_accept_feedback', accept_feedback)
    assert is_feedback_ready(None, slot.submission) is result


@pytest.mark.django_db
@pytest.mark.parametrize('agenda_visible,result', (
    (True, True),
    (False, False),
))
def test_agenda_permission_is_speaker_viewable(agenda_visible, result, speaker, slot, schedule, monkeypatch):
    monkeypatch.setattr('pretalx.agenda.permissions.is_agenda_visible', lambda x, y: agenda_visible)
    assert is_speaker_viewable(None, speaker.profiles.first()) is result
