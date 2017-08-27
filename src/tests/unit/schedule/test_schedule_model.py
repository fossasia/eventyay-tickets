import datetime

import pytest

from pretalx.schedule.models import Schedule, TalkSlot


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


@pytest.mark.django_db
def test_freeze_cache(talk_slot):
    talk_slot.event.wip_schedule.freeze('Version')
    # make sure the cache for wip_schedule is invalidated
    assert talk_slot.event.wip_schedule.version is None


@pytest.mark.django_db
def test_scheduled_talks(talk_slot, room):
    assert talk_slot.schedule.scheduled_talks.count() == 0
    talk_slot.room = room
    talk_slot.start = datetime.datetime.now()
    talk_slot.save()
    assert talk_slot.schedule.scheduled_talks.count() == 1
