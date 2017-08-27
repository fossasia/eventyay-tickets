import json

import pytest
from django.urls import reverse

from pretalx.schedule.models import Schedule


@pytest.mark.django_db
@pytest.mark.usefixtures('room')
def test_room_list(orga_client, event):
    response = orga_client.get(reverse(f'orga:schedule.api.rooms', kwargs={'event': event.slug}), follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['rooms']) == 1
    assert content['rooms'][0]['name']
    assert content['start']
    assert content['end']


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
def test_talk_list(orga_client, event):
    response = orga_client.get(reverse(f'orga:schedule.api.talks', kwargs={'event': event.slug}), follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1
    assert content['results'][0]['title']


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


# TODO: test talk update view
