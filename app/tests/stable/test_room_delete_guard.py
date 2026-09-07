import datetime as dt

import pytest
from django.contrib.messages import get_messages
from django.utils import timezone
from django_scopes import scope

from eventyay.base.models import Room, Submission
from eventyay.base.models.room import linked_submission_talks
from eventyay.base.models.slot import TalkSlot


WARNING_TEXT = 'This room has linked schedules/sessions'
GENERIC_DELETE_TEXT = 'Please make sure that this is the item you want to delete'


def schedule_session(event, room, title='Opening Keynote'):
    """Schedule a submission in the given room and return its talk slot."""
    with scope(event=event):
        submission = Submission.objects.create(
            event=event,
            title=title,
            submission_type=event.submission_types.first(),
        )
        start = timezone.now() + dt.timedelta(days=30)
        return TalkSlot.objects.create(
            room=room,
            schedule=event.wip_schedule,
            submission=submission,
            start=start,
            end=start + dt.timedelta(hours=1),
        )


@pytest.fixture
def empty_room(db, event):
    with scope(event=event):
        return Room.objects.create(event=event, name='Empty Side Room', position=2)


@pytest.mark.django_db
def test_linked_submission_talks_lists_scheduled_talks(event, room, empty_room):
    slot = schedule_session(event, room)

    assert linked_submission_talks(room) == [slot]
    assert linked_submission_talks(empty_room) == []


@pytest.mark.django_db
def test_linked_submission_talks_lists_each_session_once(event, room):
    """A session has a slot per schedule version, but should be listed once."""
    slot = schedule_session(event, room)
    with scope(event=event):
        event.wip_schedule.freeze(name='v1', notify_speakers=False)
        assert (
            TalkSlot.objects.filter(room=room, submission=slot.submission).count() > 1
        )

    talks = linked_submission_talks(room)

    assert [talk.submission_id for talk in talks] == [slot.submission_id]


@pytest.mark.django_db
def test_delete_confirmation_warns_about_linked_sessions(organizer_client, event, room):
    schedule_session(event, room)
    with scope(event=event):
        url = room.urls.delete

    response = organizer_client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert WARNING_TEXT in content
    assert 'Opening Keynote' in content
    # The confirmation form must not be offered for a room that cannot be deleted.
    assert GENERIC_DELETE_TEXT not in content
    assert 'fa-trash' not in content


@pytest.mark.django_db
def test_delete_confirmation_is_unchanged_for_room_without_sessions(organizer_client, event, empty_room):
    with scope(event=event):
        url = empty_room.urls.delete

    response = organizer_client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert WARNING_TEXT not in content
    assert GENERIC_DELETE_TEXT in content
    assert 'fa-trash' in content


@pytest.mark.django_db
def test_delete_is_refused_while_sessions_are_scheduled(organizer_client, event, room):
    schedule_session(event, room)
    with scope(event=event):
        url = room.urls.delete

    response = organizer_client.post(url)

    assert response.status_code == 302
    with scope(event=event):
        room.refresh_from_db()
        assert room.deleted is False
        assert Room.objects.filter(pk=room.pk, deleted=False).exists()
    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert any(WARNING_TEXT in message for message in messages)


@pytest.mark.django_db
def test_delete_still_works_for_room_without_sessions(organizer_client, event, empty_room):
    with scope(event=event):
        url = empty_room.urls.delete

    response = organizer_client.post(url)

    assert response.status_code == 302
    with scope(event=event):
        empty_room.refresh_from_db()
        assert empty_room.deleted is True
