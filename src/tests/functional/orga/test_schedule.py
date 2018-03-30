import json
from datetime import datetime

import pytest
import pytz
from django.urls import reverse
from django.utils.timezone import now

from pretalx.schedule.models import Availability, Schedule, TalkSlot


@pytest.mark.django_db
@pytest.mark.usefixtures('room')
def test_room_list(orga_client, event, room_availability):
    response = orga_client.get(reverse(f'orga:schedule.api.rooms', kwargs={'event': event.slug}), follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['rooms']) == 1
    assert content['rooms'][0]['name']
    assert content['start']
    assert content['end']
    availabilities = content['rooms'][0]['availabilities']
    assert len(availabilities) == 1
    assert availabilities[0]['id'] == room_availability.pk
    assert availabilities[0]['start']
    assert availabilities[0]['end']


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
def test_talk_list(orga_client, event):
    response = orga_client.get(reverse(f'orga:schedule.api.talks', kwargs={'event': event.slug}), follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1
    assert content['results'][0]['title']


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission', 'slot')
def test_talk_list_with_filter(orga_client, event, schedule):
    response = orga_client.get(
        reverse(f'orga:schedule.api.talks', kwargs={'event': event.slug}),
        data={'version': schedule.version},
        follow=True,
    )
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 2
    assert content['results'][0]['title']


@pytest.mark.django_db
def test_talk_schedule_api_update(orga_client, event, schedule, slot, room):
    slot = event.wip_schedule.talks.first()
    start = now()
    assert slot.start != start
    response = orga_client.patch(
        reverse(f'orga:schedule.api.update', kwargs={'event': event.slug, 'pk': slot.pk}),
        data=json.dumps({'room': room.pk, 'start': start.isoformat()}),
        follow=True,
    )
    slot.refresh_from_db()
    content = json.loads(response.content.decode())
    assert content['title'] == slot.submission.title
    assert slot.start == start
    assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_reset(orga_client, event, schedule, slot, room):
    slot = event.wip_schedule.talks.first()
    slot.start = now()
    slot.room = room
    slot.save()
    assert slot.start
    response = orga_client.patch(
        reverse(f'orga:schedule.api.update', kwargs={'event': event.slug, 'pk': slot.pk}),
        data=json.dumps(dict()),
        follow=True,
    )
    slot.refresh_from_db()
    content = json.loads(response.content.decode())
    assert content['title'] == slot.submission.title
    assert not slot.start
    assert not slot.room


@pytest.mark.usefixtures('accepted_submission')
@pytest.mark.django_db
def test_api_availabilities(orga_client, event, room, speaker, confirmed_submission):
    talk = TalkSlot.objects.get(submission=confirmed_submission)
    Availability.objects.create(event=event, room=room, start=datetime(2017, 1, 1, 1, tzinfo=pytz.utc), end=datetime(2017, 1, 1, 5, tzinfo=pytz.utc))
    Availability.objects.create(event=event, person=speaker.profiles.first(), start=datetime(2017, 1, 1, 3, tzinfo=pytz.utc), end=datetime(2017, 1, 1, 6, tzinfo=pytz.utc))

    response = orga_client.get(
        reverse(f'orga:schedule.api.availabilities', kwargs={
            'event': event.slug,
            'talkid': talk.pk,
            'roomid': room.pk
        }), follow=True
    )

    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1
    assert content['results'][0]['start'] == '2017-01-01 03:00:00+00:00'
    assert content['results'][0]['end'] == '2017-01-01 05:00:00+00:00'


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
@pytest.mark.usefixtures('room')
def test_orga_can_see_schedule(orga_client, event):
    response = orga_client.get(event.orga_urls.schedule, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
@pytest.mark.usefixtures('room')
@pytest.mark.xfail
def test_orga_can_release_and_reset_schedule(orga_client, event):
    assert Schedule.objects.count() == 1
    response = orga_client.post(event.orga_urls.release_schedule, follow=True, data={'version': 'Test version 2'})
    assert response.status_code == 200
    assert Schedule.objects.count() == 2
    assert Schedule.objects.get(version='Test version 2')
    response = orga_client.post(event.orga_urls.reset_schedule, follow=True, data={'version': 'Test version 2'})
    assert response.status_code == 200
    assert Schedule.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
@pytest.mark.usefixtures('room')
def test_orga_cannot_reuse_schedule_name(orga_client, event):
    assert Schedule.objects.count() == 1
    response = orga_client.post(event.orga_urls.release_schedule, follow=True, data={'version': 'Test version 2'})
    assert response.status_code == 200
    assert Schedule.objects.count() == 2
    assert Schedule.objects.get(version='Test version 2')
    response = orga_client.post(event.orga_urls.release_schedule, follow=True, data={'version': 'Test version 2'})
    assert response.status_code == 200
    assert Schedule.objects.count() == 2


@pytest.mark.django_db
def test_orga_can_toggle_schedule_visibility(orga_client, event):
    from pretalx.event.models import Event
    assert event.settings.show_schedule is True

    response = orga_client.get(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.show_schedule is False

    response = orga_client.get(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.show_schedule is True


@pytest.mark.django_db
def test_create_room(orga_client, event, availability):
    assert event.rooms.count() == 0
    response = orga_client.post(
        event.orga_urls.new_room,
        follow=True,
        data={
            'name_0': 'A room',
            'availabilities': json.dumps({
                'availabilities': [
                    {
                        'start': availability.start.strftime('%Y-%m-%d %H:%M:00Z'),
                        'end': availability.end.strftime('%Y-%m-%d %H:%M:00Z'),
                    }
                ]
            })
        }
    )
    assert response.status_code == 200
    assert event.rooms.count() == 1
    assert str(event.rooms.first().name) == 'A room'
    assert event.rooms.first().availabilities.count() == 1
    assert event.rooms.first().availabilities.first().start == availability.start


@pytest.mark.django_db
@pytest.mark.usefixtures('room_availability')
def test_edit_room(orga_client, event, room):
    assert event.rooms.count() == 1
    assert event.rooms.first().availabilities.count() == 1
    assert str(event.rooms.first().name) != 'A room'
    response = orga_client.post(
        room.urls.edit,
        follow=True,
        data={'name_0': 'A room', 'availabilities': '{"availabilities": []}'}
    )
    assert response.status_code == 200
    assert event.rooms.count() == 1
    assert str(event.rooms.first().name) == 'A room'
    assert event.rooms.first().availabilities.count() == 0


@pytest.mark.django_db
def test_delete_room(orga_client, event, room):
    assert event.rooms.count() == 1
    response = orga_client.get(
        room.urls.delete,
        follow=True,
    )
    assert response.status_code == 200
    assert event.rooms.count() == 0


@pytest.mark.django_db
def test_delete_used_room(orga_client, event, room, slot):
    assert event.rooms.count() == 1
    assert slot.room == room
    response = orga_client.get(
        room.urls.delete,
        follow=True,
    )
    assert response.status_code == 200
    assert event.rooms.count() == 1
