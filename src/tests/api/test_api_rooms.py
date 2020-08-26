import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.room import RoomOrgaSerializer, RoomSerializer


@pytest.mark.django_db
def test_room_serializer(room):
    data = RoomSerializer(room).data
    assert set(data.keys()) == {
        "id",
        "name",
        "description",
        "capacity",
        "position",
        "url",
    }
    assert data["id"] == room.pk


@pytest.mark.django_db
def test_room_orga_serializer(room):
    with scope(event=room.event):
        data = RoomOrgaSerializer(room).data
        assert set(data.keys()) == {
            "id",
            "name",
            "description",
            "capacity",
            "position",
            "speaker_info",
            "availabilities",
            "url",
        }
        assert data["id"] == room.pk


@pytest.mark.django_db
def test_not_everybody_can_see_rooms(client, room):
    response = client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content["results"]) == 0, content


@pytest.mark.django_db
def test_everybody_can_see_published_rooms(client, room, slot):
    room.event.is_public = True
    room.event.save()
    response = client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_orga_can_see_room_speaker_info(orga_client, room):
    response = orga_client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content["results"]) == 1, content
    assert "speaker_info" in content["results"][0]
