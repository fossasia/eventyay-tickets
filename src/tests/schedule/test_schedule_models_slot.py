import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from pretalx.schedule.models import TalkSlot


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start,end,duration,has_submission",
    (
        (None, None, "sub", True),
        (0, None, "sub", True),
        (None, 0, "sub", True),
        (0, 1, 1, True),
        (None, None, None, False),
        (0, None, None, False),
        (None, 0, None, False),
        (0, 1, 1, False),
    ),
)
def test_slot_duration(submission, start, end, duration, has_submission):
    _now = now()
    if start is not None:
        start = _now + dt.timedelta(minutes=start)
    if end is not None:
        end = _now + dt.timedelta(minutes=end)
    slot = TalkSlot(
        start=start, end=end, submission=submission if has_submission else None
    )
    if duration == "sub":
        assert slot.duration == submission.get_duration()
    else:
        assert slot.duration == duration


@pytest.mark.django_db
def test_slot_string(slot, room):
    str(slot)
    str(room)


@pytest.mark.django_db
def test_slot_build_empty_ical(slot):
    slot.room = None
    assert not slot.build_ical(None)


@pytest.mark.django_db
def test_slot_warnings_without_room(slot):
    with scope(event=slot.event):
        slot.room = None
        slot.save()
        assert slot.start
        assert not slot.schedule.get_talk_warnings(slot)


@pytest.mark.django_db
def test_slot_warnings_when_room_unavailable(slot, room_availability):
    with scope(event=slot.event):
        slot.start = room_availability.end
        slot.end = slot.start + dt.timedelta(minutes=30)
        slot.save()
        warnings = slot.schedule.get_talk_warnings(slot)
        assert len(warnings) == 1
        assert warnings[0]["type"] == "room"


@pytest.mark.django_db
def test_slot_no_warnings_when_room_available(slot, room_availability):
    with scope(event=slot.event):
        warnings = slot.schedule.get_talk_warnings(slot)
        assert not warnings


@pytest.mark.django_db
def test_slot_warning_when_speaker_unavailable(slot, availability, room_availability):
    with scope(event=slot.event):
        availability.start -= dt.timedelta(days=7)
        availability.end -= dt.timedelta(days=7)
        availability.person = slot.submission.speakers.first().event_profile(slot.event)
        availability.pk = None
        availability.save()
        warnings = slot.schedule.get_talk_warnings(slot)
        assert len(warnings) == 1
        assert warnings[0]["type"] == "speaker"
        assert (
            warnings[0]["message"]
            == "Jane Speaker is not available at the scheduled time."
        )


@pytest.mark.django_db
def test_slot_warning_when_speaker_overbooked(
    slot, availability, other_slot, room_availability
):
    with scope(event=slot.event):
        availability.person = slot.submission.speakers.first().event_profile(slot.event)
        availability.pk = None
        availability.save()
        other_slot.start = slot.start + dt.timedelta(minutes=10)
        other_slot.end = slot.end - dt.timedelta(minutes=10)
        other_slot.submission.speakers.add(availability.person.user)
        other_slot.save()
        other_slot.submission.save()
        warnings = slot.schedule.get_talk_warnings(slot)
        assert len(warnings) == 2
        assert warnings[0]["type"] == "room_overlap"
        assert (
            warnings[0]["message"]
            == "Another session in the same room overlaps with this one."
        )
        assert warnings[1]["type"] == "speaker"
        assert (
            warnings[1]["message"]
            == "Jane Speaker is scheduled for another session at the same time."
        )
