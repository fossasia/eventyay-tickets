import icalendar
import pytest


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
