from datetime import timedelta

import pytest
from django.core import mail as djmail
from django.utils.timezone import now
from django_scopes import scope

from pretalx.mail.models import QueuedMail
from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.models import Submission


@pytest.mark.django_db
def test_copy_to_schedule(slot):
    with scope(event=slot.submission.event):
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
    with scope(event=slot.submission.event):
        slot_count = TalkSlot.objects.count()
        schedule_count = Schedule.objects.count()
        old, new = slot.submission.event.wip_schedule.freeze('Version')
        assert TalkSlot.objects.count() == slot_count + 1
        assert Schedule.objects.count() == schedule_count + 1
        assert old.talks.count() == 1
        assert new.talks.count() == 1
        assert old.version == 'Version'
        assert not new.version


@pytest.mark.parametrize('version', ['wip', 'latest', None, ''])
@pytest.mark.django_db
def test_freeze_fail(slot, schedule, version):
    with scope(event=slot.submission.event):
        schedule_count = Schedule.objects.count()
        with pytest.raises(Exception):
            old, new = slot.submission.event.wip_schedule.freeze(version if version is not None else schedule.version)
        assert Schedule.objects.count() == schedule_count


@pytest.mark.django_db
def test_freeze_fail_repeat(slot, schedule):
    with scope(event=slot.submission.event):
        schedule_count = Schedule.objects.count()
        old, new = slot.submission.event.wip_schedule.freeze('version')
        assert Schedule.objects.count() == schedule_count + 1
        with pytest.raises(Exception):
            old.freeze('version')
        assert Schedule.objects.count() == schedule_count + 1


@pytest.mark.django_db
def test_freeze_cache(slot):
    with scope(event=slot.submission.event):
        slot.event.wip_schedule.freeze('Version')
        # make sure the cache for wip_schedule is invalidated
        assert slot.event.wip_schedule.version is None


@pytest.mark.django_db
def test_unfreeze(slot):
    event = slot.event
    with scope(event=event):
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

    with scope(event=event):
        schedule1, _ = event.wip_schedule.freeze('Version 1')

        sub = Submission.objects.create(title='Submission 2', event=event, submission_type=event.cfp.default_type)
        TalkSlot.objects.create(submission=sub, room=slot.room, schedule=event.wip_schedule, is_visible=True)
        schedule2, _ = event.wip_schedule.freeze('Version 2')

        schedule1.unfreeze()

        assert event.wip_schedule.talks.count() == 2
        # make sure the cache for wip_schedule is invalidated
        assert event.wip_schedule.version is None


@pytest.mark.django_db
def test_unfreeze_unreleased_schedule(event):
    with scope(event=event):
        with pytest.raises(Exception):
            event.wip_schedule.unfreeze()


@pytest.mark.django_db
def test_scheduled_talks(slot, room):
    with scope(event=slot.submission.event):
        slot_count = slot.schedule.scheduled_talks.count()
        current_slot = slot.submission.slots.filter(schedule__version__isnull=True).first()
        current_slot.room = slot.room
        current_slot.start = now()
        current_slot.save()
        old, new = current_slot.schedule.freeze('test-version')
        assert new.scheduled_talks.count() == slot_count
        current_slot = current_slot.submission.slots.filter(schedule__version__isnull=True).first()
        current_slot.room = None
        current_slot.start = now()
        current_slot.save()
        old, new = current_slot.schedule.freeze('test-version2')
        assert new.scheduled_talks.count() == slot_count - 1


@pytest.mark.django_db
def test_is_archived(event):
    with scope(event=event):
        event.release_schedule(name='v1')
        event.release_schedule(name='v2')

        v1_schedule = Schedule.objects.get(version='v1')
        v2_schedule = Schedule.objects.get(version='v2')
        unreleased_schedule = event.schedules.filter(version=None).first()

        assert v1_schedule.is_archived
        assert not v2_schedule.is_archived
        assert not unreleased_schedule.is_archived


@pytest.mark.django_db
def test_schedule_changes(event, slot, room, accepted_submission):
    with scope(event=slot.submission.event):
        djmail.outbox = []
        QueuedMail.objects.filter(sent__isnull=True).update(sent=now())
        assert slot.schedule != event.wip_schedule
        current_slot = slot.submission.slots.get(schedule=event.wip_schedule)
        current_slot.room = room
        current_slot.start = slot.start
        current_slot.end = slot.end
        current_slot.save()
        assert event.wip_schedule.talks.all().count() == 2
        slot.room = None
        slot.start = None
        slot.end = None
        slot.is_visible = False
        slot.save()
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
        schedule, _ = event.wip_schedule.freeze('test')
        assert schedule.changes == {
            'count': 1,
            'action': 'update',
            'new_talks': [current_slot],
            'canceled_talks': [],
            'moved_talks': [],
        }
        assert len(djmail.outbox) == 0
        mail_count = QueuedMail.objects.filter(sent__isnull=True).count()
        assert mail_count == slot.submission.speakers.count()

        current_slot = slot.submission.slots.get(schedule=event.wip_schedule, start=current_slot.start)
        current_slot.submission.event.submit_multiple_times = True
        current_slot.submission.slot_count = 2
        current_slot.submission.save()
        current_slot.submission.update_talk_slots()
        assert current_slot.submission.slots.filter(schedule=event.wip_schedule).count() == 2
        assert event.wip_schedule.talks.all().count() == 3
        second_slot = slot.submission.slots.exclude(pk=current_slot.pk).filter(schedule=slot.submission.event.wip_schedule).get()
        second_slot.room = room
        second_slot.start = current_slot.start + timedelta(hours=2)
        second_slot.end = current_slot.end + timedelta(hours=2)
        second_slot.save()
        schedule, _ = event.wip_schedule.freeze('test2')
        assert schedule.changes == {
            'count': 1,
            'action': 'update',
            'new_talks': [second_slot],
            'canceled_talks': [],
            'moved_talks': [],
        }
        mail_count = QueuedMail.objects.filter(sent__isnull=True).count()
        assert mail_count == slot.submission.speakers.count() * 2

        for slot in event.wip_schedule.talks.filter(start__isnull=False).order_by('-pk'):
            slot.start += timedelta(hours=1)
            slot.save()
        schedule, _ = event.wip_schedule.freeze('test3')
        assert schedule.changes['count'] == 2
        assert len(schedule.changes['moved_talks']) == 2

        removed = slot.submission.slots.filter(schedule=event.wip_schedule).first()
        removed.room = None
        removed.start = None
        removed.end = None
        removed.save()
        schedule, _ = event.wip_schedule.freeze('test4')
        assert schedule.changes['count'] == 1
        assert len(schedule.changes['canceled_talks']) == 1
