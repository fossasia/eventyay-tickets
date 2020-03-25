import datetime as dt

import pytest
from django.utils.timezone import now

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
