import pytest
from django.utils.timezone import now

from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.models import Submission


@pytest.mark.django_db
def test_copy_to_schedule(slot):
    slot_count = TalkSlot.objects.count()
    schedule_count = Schedule.objects.count()
    new_schedule = Schedule.objects.create(event=slot.submission.event, version='Version')
    new_slot = slot.copy_to_schedule(new_schedule)
    assert TalkSlot.objects.count() == slot_count + 1
    assert Schedule.objects.count() == schedule_count + 1
    assert new_slot
    assert new_slot.submission == slot.submission
    assert new_slot.room == slot.room
    assert new_slot.start == slot.start
    assert new_slot.end == slot.end
    assert new_slot.event == slot.event
    assert new_slot.schedule == new_schedule


@pytest.mark.django_db
def test_freeze(slot):
    slot_count = TalkSlot.objects.count()
    schedule_count = Schedule.objects.count()
    old, new = slot.submission.event.wip_schedule.freeze('Version')
    assert TalkSlot.objects.count() == slot_count + 1
    assert Schedule.objects.count() == schedule_count + 1
    assert old.talks.count() == 1
    assert new.talks.count() == 1
    assert old.version == 'Version'
    assert not new.version


@pytest.mark.django_db
def test_freeze_cache(slot):
    slot.event.wip_schedule.freeze('Version')
    # make sure the cache for wip_schedule is invalidated
    assert slot.event.wip_schedule.version is None


@pytest.mark.django_db
def test_unfreeze(slot):
    event = slot.event
    schedule_count = event.schedules.exclude(version=None).count()
    current_slot = slot.submission.slots.filter(schedule=slot.submission.event.wip_schedule).first()
    current_slot.room = slot.room
    current_slot.save()

    old1, new1 = slot.submission.event.wip_schedule.freeze('Version 1')
    talk_slot2 = event.wip_schedule.talks.first()
    talk_slot2.room = None
    talk_slot2.save()
    old2, new2 = event.wip_schedule.freeze('Version 2')

    assert new1 == old2

    schedules = event.schedules.exclude(version=None).order_by('-published')
    assert len(schedules) == schedule_count + 2
    assert schedules[1].version == 'Version 1'
    assert schedules[0].version == 'Version 2'

    assert schedules[1].talks.first().room
    assert not schedules[0].talks.first().room


@pytest.mark.django_db
def test_unfreeze_bug72(slot):
    # https://github.com/pretalx/pretalx/issues/72
    event = slot.event

    schedule1, _ = event.wip_schedule.freeze('Version 1')

    sub = Submission.objects.create(title='Submission 2', event=event, submission_type=event.cfp.default_type)
    TalkSlot.objects.create(submission=sub, room=slot.room, schedule=event.wip_schedule, is_visible=True)
    schedule2, _ = event.wip_schedule.freeze('Version 2')

    schedule1.unfreeze()

    assert event.wip_schedule.talks.count() == 2
    # make sure the cache for wip_schedule is invalidated
    assert event.wip_schedule.version is None


@pytest.mark.django_db
def test_scheduled_talks(slot, room):
    slot_count = slot.schedule.scheduled_talks.count()
    current_slot = slot.submission.slots.filter(schedule=slot.submission.event.wip_schedule).first()
    current_slot.room = slot.room
    current_slot.start = now()
    current_slot.save()
    assert current_slot.schedule.scheduled_talks.count() == slot_count
    current_slot = current_slot.submission.slots.filter(schedule=slot.submission.event.wip_schedule).first()
    current_slot.room = None
    current_slot.start = now()
    current_slot.save()
    assert current_slot.schedule.scheduled_talks.count() == slot_count - 1
