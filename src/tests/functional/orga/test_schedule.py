import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.usefixtures('room')
def test_room_list(orga_client, event):
    response = orga_client.get(reverse(f'orga:schedule.api.rooms', kwargs={'event': event.slug}), follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1
    assert content['results'][0]['name']


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
def test_talk_list(orga_client, event):
    response = orga_client.get(reverse(f'orga:schedule.api.talks', kwargs={'event': event.slug}), follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1
    assert content['results'][0]['title']
