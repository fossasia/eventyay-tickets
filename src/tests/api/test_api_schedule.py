import json

import pytest
from django_scopes import scope


@pytest.mark.django_db
def test_user_can_see_schedule(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1


@pytest.mark.django_db
def test_user_cannot_see_wip_schedule(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules + "wip", follow=True)
    json.loads(response.content.decode())
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_see_schedule_if_not_public(client, slot, event):
    slot.submission.event.settings.set("show_schedule", False)
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 0


@pytest.mark.django_db
def test_orga_can_see_schedule(orga_client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 2


@pytest.mark.django_db
def test_orga_can_see_wip_schedule(orga_client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(
        slot.submission.event.api_urls.schedules + "wip", follow=True
    )
    json.loads(response.content.decode())
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_see_current_schedule(orga_client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(
        slot.submission.event.api_urls.schedules + "latest", follow=True
    )
    json.loads(response.content.decode())
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_cannot_see_schedule_even_if_not_public(orga_client, slot, event):
    slot.submission.event.settings.set("show_schedule", False)
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 2
