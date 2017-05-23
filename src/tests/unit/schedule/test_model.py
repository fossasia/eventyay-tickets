import pytest

from pretalx.event.models import Event
from pretalx.schedule.models import Room, Schedule, TalkSlot
from pretalx.submission.models import Submission


@pytest.fixture
def talk_slot():
    event = Event.objects.create(name='Event')
    schedule = event.schedules.first()
    sub = Submission.objects.create(title='Submission', event=schedule.event, submission_type=event.cfp.default_type)
    room = Room.objects.create(name='Room', event=schedule.event)
    return TalkSlot.objects.create(submission=sub, room=room, schedule=schedule)


@pytest.mark.django_db
def test_copy_to_schedule(talk_slot):
    assert TalkSlot.objects.count() == 1
    assert Schedule.objects.count() == 1
    new_schedule = Schedule.objects.create(event=talk_slot.submission.event, version='Version')
    new_slot = talk_slot.copy_to_schedule(new_schedule)
    assert TalkSlot.objects.count() == 2
    assert Schedule.objects.count() == 2
    assert new_slot
    assert new_slot.submission == talk_slot.submission
    assert new_slot.room == talk_slot.room
    assert new_slot.start == talk_slot.start
    assert new_slot.end == talk_slot.end
    assert new_slot.event == talk_slot.event
    assert new_slot.schedule == new_schedule


@pytest.mark.django_db
def test_freeze(talk_slot):
    assert TalkSlot.objects.count() == 1
    assert Schedule.objects.count() == 1
    old, new = talk_slot.schedule.freeze('Version')
    assert TalkSlot.objects.count() == 2
    assert Schedule.objects.count() == 2
    assert old.talks.count() == 1
    assert new.talks.count() == 1
    assert old.version == 'Version'
    assert not new.version
