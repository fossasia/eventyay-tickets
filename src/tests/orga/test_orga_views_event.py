import json

import pytest


@pytest.mark.django_db
def test_organiser_can_see_event_suggestions(orga_client, event):
    response = orga_client.get('/orga/event/typeahead/')
    assert response.status_code == 200
    content = json.loads(response.content.decode())['results']
    assert len(content) == 1
    assert content[0]['id'] == event.id


@pytest.mark.django_db
def test_speaker_cannot_see_event_suggestions(speaker_client, event):
    response = speaker_client.get('/orga/event/typeahead/')
    assert response.status_code == 200
    content = json.loads(response.content.decode())['results']
    assert len(content) == 0
