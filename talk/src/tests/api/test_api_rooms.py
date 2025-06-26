import json
from datetime import datetime, timedelta

import dateutil.parser
import pytest
from django_scopes import scope

from pretalx.api.serializers.room import RoomOrgaSerializer, RoomSerializer
from pretalx.api.versions import LEGACY


@pytest.mark.django_db
def test_room_serializer(room):
    data = RoomSerializer(room).data
    assert set(data.keys()) == {
        "id",
        "guid",
        "name",
        "description",
        "capacity",
        "position",
        "uuid",
    }
    assert data["id"] == room.pk


@pytest.mark.django_db
def test_room_orga_serializer(room):
    with scope(event=room.event):
        data = RoomOrgaSerializer(room).data
        assert set(data.keys()) == {
            "id",
            "guid",
            "name",
            "description",
            "capacity",
            "position",
            "speaker_info",
            "availabilities",
            "uuid",
        }
        assert data["id"] == room.pk


@pytest.mark.django_db
def test_cannot_see_rooms(client, room):
    response = client.get(room.event.api_urls.rooms, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_can_see_rooms_public_event(client, room, slot):
    with scope(event=room.event):
        room.event.is_public = True
        room.event.save()
    response = client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["name"]["en"] == room.name


@pytest.mark.django_db
def test_orga_can_see_rooms(client, orga_user_token, room):
    response = client.get(
        room.event.api_urls.rooms,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["name"]["en"] == room.name


@pytest.mark.django_db
def test_orga_can_see_single_room(client, orga_user_token, room):
    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["name"]["en"] == room.name
    assert isinstance(content["name"], dict)


@pytest.mark.django_db
def test_orga_can_see_single_room_locale_override(client, orga_user_token, room):
    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/?lang=en",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert isinstance(content["name"], str)


@pytest.mark.django_db
def test_legacy_room_api(client, orga_user_token, room):

    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["id"] == room.pk
    assert "url" in content
    assert "uuid" not in content
    orga_user_token.refresh_from_db()
    assert orga_user_token.version == "LEGACY"


@pytest.mark.django_db
def test_invalid_api_version(client, orga_user_token, room):

    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": "YOLO",
        },
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert "id" not in content
    orga_user_token.refresh_from_db()
    assert not orga_user_token.version


@pytest.mark.django_db
def test_orga_can_create_rooms(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.rooms,
        follow=True,
        data={"name": "newtestroom", "capacity": 100},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        room = event.rooms.get(name="newtestroom")
        assert room.logged_actions().filter(action_type="pretalx.room.create").exists()


@pytest.mark.django_db
def test_orga_cannot_create_rooms_readonly_token(client, orga_user_token, event):
    response = client.post(
        event.api_urls.rooms,
        follow=True,
        data={"name": "newtestroom"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.rooms.filter(name="newtestroom").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.room.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_rooms(client, orga_user_write_token, event, room):
    assert room.name != "newtestroom"
    response = client.patch(
        event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        data=json.dumps({"name": "newtestroom"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=room.event):
        room.refresh_from_db()
        assert room.name == "newtestroom"
        assert room.logged_actions().filter(action_type="pretalx.room.update").exists()


@pytest.mark.django_db
def test_orga_cannot_update_rooms_readonly_token(client, orga_user_token, room):
    response = client.patch(
        room.event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        data=json.dumps({"name": "newtestroom"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=room.event):
        room.refresh_from_db()
        assert room.name != "newtestroom"
        assert (
            not room.logged_actions().filter(action_type="pretalx.room.update").exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_rooms(client, orga_user_write_token, event, room):
    response = client.delete(
        event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=room.event):
        assert event.rooms.all().count() == 0
        assert event.logged_actions().filter(action_type="pretalx.room.delete").exists()


@pytest.mark.django_db
def test_orga_cannot_delete_rooms_readonly_token(client, orga_user_token, room):
    response = client.delete(
        room.event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=room.event):
        assert room.event.rooms.all().count() == 1


@pytest.mark.django_db
def test_orga_can_create_room_with_availabilities(client, orga_user_write_token, event):
    start = datetime.combine(event.date_from, datetime.min.time()).replace(
        tzinfo=event.tz
    )
    end = start + timedelta(hours=2)

    response = client.post(
        event.api_urls.rooms,
        follow=True,
        data=json.dumps(
            {
                "name": "Room with Availabilities",
                "availabilities": [
                    {"start": start.isoformat(), "end": end.isoformat()}
                ],
            }
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    data = json.loads(response.text)
    assert "availabilities" in data
    assert len(data["availabilities"]) == 1
    assert dateutil.parser.isoparse(data["availabilities"][0]["start"]) == start
    assert dateutil.parser.isoparse(data["availabilities"][0]["end"]) == end

    with scope(event=event):
        room = event.rooms.get(name="Room with Availabilities")
        assert room.availabilities.count() == 1
        assert room.availabilities.first().start == start
        assert room.availabilities.first().end == end


@pytest.mark.django_db
def test_orga_can_update_room_availabilities(client, orga_user_write_token, room):

    event = room.event
    start1 = datetime.combine(event.date_from, datetime.min.time()).replace(
        tzinfo=event.tz
    )
    end1 = start1 + timedelta(hours=2)
    start2 = start1 + timedelta(hours=3)
    end2 = start2 + timedelta(hours=2)

    response = client.patch(
        event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        data=json.dumps(
            {"availabilities": [{"start": start1.isoformat(), "end": end1.isoformat()}]}
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200

    response = client.patch(
        event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        data=json.dumps(
            {"availabilities": [{"start": start2.isoformat(), "end": end2.isoformat()}]}
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200
    data = json.loads(response.text)

    assert len(data["availabilities"]) == 1

    assert dateutil.parser.isoparse(data["availabilities"][0]["start"]) == start2
    assert dateutil.parser.isoparse(data["availabilities"][0]["end"]) == end2

    with scope(event=event):
        room.refresh_from_db()
        assert room.availabilities.count() == 1
        assert room.availabilities.first().start == start2
        assert room.availabilities.first().end == end2


@pytest.mark.django_db
def test_orga_can_remove_room_availabilities(client, orga_user_write_token, room):
    event = room.event
    start = datetime.combine(event.date_from, datetime.min.time())
    end = start + timedelta(hours=2)

    response = client.patch(
        event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        data=json.dumps(
            {"availabilities": [{"start": start.isoformat(), "end": end.isoformat()}]}
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200

    response = client.patch(
        event.api_urls.rooms + f"{room.pk}/",
        follow=True,
        data=json.dumps({"availabilities": []}),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200
    data = json.loads(response.text)
    assert data["availabilities"] == []

    with scope(event=event):
        room.refresh_from_db()
        assert room.availabilities.count() == 0


@pytest.mark.django_db
def test_room_availability_uses_event_timezone(client, orga_user_write_token, event):
    """Test that room availability times are shown in the event's timezone."""

    event.timezone = "Europe/Berlin"
    event.save()
    start = datetime.combine(event.date_from, datetime.min.time())
    end = start + timedelta(hours=2)

    response = client.post(
        event.api_urls.rooms,
        follow=True,
        data=json.dumps(
            {
                "name": "Room with Timezone Test",
                "availabilities": [
                    {"start": start.isoformat(), "end": end.isoformat()}
                ],
            }
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )

    assert response.status_code == 201
    data = json.loads(response.text)

    assert "Z" not in data["availabilities"][0]["start"]
    assert "+00:00" not in data["availabilities"][0]["end"]


@pytest.mark.django_db
def test_orga_can_create_overlapping_availabilities(
    client, orga_user_write_token, event
):

    start1 = datetime.combine(event.date_from, datetime.min.time()).replace(
        tzinfo=event.tz
    )
    end1 = start1 + timedelta(hours=3)
    start2 = start1 + timedelta(hours=1)
    end2 = start1 + timedelta(hours=4)

    response = client.post(
        event.api_urls.rooms,
        follow=True,
        data=json.dumps(
            {
                "name": "Room with Overlapping Availabilities",
                "availabilities": [
                    {"start": start1.isoformat(), "end": end1.isoformat()},
                    {"start": start2.isoformat(), "end": end2.isoformat()},
                ],
            }
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201
    data = json.loads(response.text)

    assert len(data["availabilities"]) == 1

    assert dateutil.parser.isoparse(data["availabilities"][0]["start"]) == start1
    assert dateutil.parser.isoparse(data["availabilities"][0]["end"]) == end2

    with scope(event=event):
        room = event.rooms.get(name="Room with Overlapping Availabilities")
        assert room.availabilities.count() == 1
        assert room.availabilities.first().start == start1
        assert room.availabilities.first().end == end2
