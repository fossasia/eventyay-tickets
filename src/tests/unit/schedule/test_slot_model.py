from datetime import timedelta

import pytest
from django.utils.timezone import now

from pretalx.schedule.models import TalkSlot


@pytest.mark.django_db
@pytest.mark.parametrize(
    'start,end,duration', (
        (None, None, 'sub'),
        (0, None, 'sub'),
        (None, 0, 'sub'),
        (0, 1, 1),
    )
)
def test_slot_duration(submission, start, end, duration):
    _now = now()
    if start is not None:
        start = now() + timedelta(minutes=start)
    if end is not None:
        end = now() + timedelta(minutes=end)
    slot = TalkSlot(start=start, end=end, submission=submission)
    if duration == 'sub':
        assert slot.duration == submission.get_duration()
    else:
        assert slot.duration == duration


@pytest.mark.django_db
def test_slot_string(slot):
    str(slot)
