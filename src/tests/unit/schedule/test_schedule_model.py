import datetime

import pytest

from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.models import Submission


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
def test_unfreeze(talk_slot):
    event = talk_slot.event

    old1, new1 = talk_slot.schedule.freeze('Version 1')
    talk_slot2 = event.wip_schedule.talks.first()
    talk_slot2.room = None
    talk_slot2.save()
    old2, new2 = event.wip_schedule.freeze('Version 2')

    assert new1 == old2

    schedules = event.schedules.exclude(version=None).order_by('published')
    assert len(schedules) == 2
    assert schedules[0].version == 'Version 1'
    assert schedules[1].version == 'Version 2'

    assert schedules[0].talks.first().room
    assert not schedules[1].talks.first().room


@pytest.mark.django_db
def test_unfreeze_bug72(talk_slot):
    # https://github.com/pretalx/pretalx/issues/72
    event = talk_slot.event

    schedule1, _ = talk_slot.schedule.freeze('Version 1')

    sub = Submission.objects.create(title='Submission 2', event=event, submission_type=event.cfp.default_type)
    TalkSlot.objects.create(submission=sub, room=talk_slot.room, schedule=event.wip_schedule, is_visible=True)
    schedule2, _ = event.wip_schedule.freeze('Version 2')

    schedule1.unfreeze()

    assert event.wip_schedule.talks.count() == 2
    # make sure the cache for wip_schedule is invalidated
    assert event.wip_schedule.version is None


@pytest.mark.django_db
def test_scheduled_talks(talk_slot, room):
    assert talk_slot.schedule.scheduled_talks.count() == 0
    talk_slot.room = room
    talk_slot.start = datetime.datetime.now()
    talk_slot.save()
    assert talk_slot.schedule.scheduled_talks.count() == 1
