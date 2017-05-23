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
