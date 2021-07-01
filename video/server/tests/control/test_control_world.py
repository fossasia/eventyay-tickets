import icalendar
import pytest
from django.test import override_settings


@pytest.mark.django_db
def test_world_redirect_unauthenticated(world, client):
    response = client.get("/control/worlds/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_world_allow_unauthenticated_with_secret_key(world, client):
    token = "foobarverysecrettoken"
    response = client.get(f"/control/worlds/?control_token={token}")
    assert response.status_code == 302
    with override_settings(CONTROL_SECRET=token):
        response = client.get(f"/control/worlds/?control_token={token}")
        assert response.status_code == 200
        assert str(world.id) in response.content.decode()


@pytest.mark.django_db
def test_world_list_shows_worlds(world, staff_client):
    response = staff_client.get("/control/worlds/")
    assert response.status_code == 200
    assert str(world.id) in response.content.decode()


@pytest.mark.django_db
def test_world_admin_token_redirect(world, staff_client):
    response = staff_client.get(f"/control/worlds/{world.id}/admin")
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(f"https://{world.domain}/#token=")
    token = location.split("=")[-1]
    assert world.decode_token(token)


@pytest.mark.django_db
def test_world_calendar(staff_client, planned_usage):
    world = planned_usage.world
    response = staff_client.get("/control/worlds/calendar")
    assert response.status_code == 200
    assert str(world.id) in response.content.decode()
    content = response.content.decode()
    calendar = icalendar.Calendar.from_ical(content)
    assert calendar
    event = calendar.subcomponents[0]
    assert world.domain in event["URL"]
