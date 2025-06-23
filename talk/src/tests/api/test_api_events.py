import json

import pytest

from pretalx.api.serializers.event import EventSerializer


@pytest.mark.django_db
def test_event_serializer(event):
    data = EventSerializer(event).data
    data["name"] = None
    assert data == {
        "name": None,
        "slug": event.slug,
        "is_public": event.is_public,
        "date_from": event.date_from.isoformat(),
        "date_to": event.date_to.isoformat(),
        "timezone": event.timezone,
        "urls": {
            "base": event.urls.base.full(),
            "schedule": event.urls.schedule.full(),
            "login": event.urls.login.full(),
            "feed": event.urls.feed.full(),
        },
    }


@pytest.mark.django_db
def test_can_only_see_public_events(client, event, other_event):
    other_event.is_public = False
    other_event.save()
    assert event.is_public
    assert not other_event.is_public

    response = client.get("/api/events", follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content) == 1, content
    assert content[0]["name"]["en"] == event.name


@pytest.mark.django_db
def test_can_only_see_public_events_in_detail(client, event):
    assert event.is_public
    response = client.get(event.api_urls.base, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["name"]["en"] == event.name

    event.is_public = False
    event.save()

    response = client.get(event.api_urls.base, follow=True)
    assert response.status_code == 404
    assert event.name not in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_nonpublic_events(orga_client, event, other_event):
    event.is_public = False
    event.save()
    assert not event.is_public
    assert other_event.is_public

    response = orga_client.get("/api/events", follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content) == 2, content
    assert content[-1]["name"]["en"] == event.name
