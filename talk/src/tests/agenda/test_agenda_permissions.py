import pytest
from django_scopes import scope

from pretalx.agenda.rules import is_agenda_visible, is_speaker_viewable


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_public,show_schedule,has_schedule,result",
    (
        (True, True, True, True),
        (True, True, False, False),
        (True, False, True, False),
        (False, True, True, False),
        (False, False, True, False),
    ),
)
def test_agenda_permission_is_agenda_visible(
    is_public, show_schedule, has_schedule, result, event
):
    with scope(event=event):
        event.is_public = is_public
        event.feature_flags["show_schedule"] = show_schedule
        event.save()
        if has_schedule:
            event.release_schedule("42")
        assert is_agenda_visible(None, event) is result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "agenda_visible,result",
    (
        (True, True),
        (False, False),
    ),
)
def test_agenda_permission_is_speaker_viewable(
    agenda_visible, result, speaker, slot, event
):
    with scope(event=event):
        assert slot.schedule == event.current_schedule
        slot.is_visible = agenda_visible
        slot.save()
    with scope(event=event):
        assert is_speaker_viewable(None, speaker.profiles.first()) is result
