import pytest


@pytest.mark.django_db
def test_detect_world(client, world):
    r = client.get("/foo", HTTP_HOST="foobar.com")
    assert r.status_code == 404

    world.domain = "foobar.com"
    world.save()

    r = client.get("/foo", HTTP_HOST="foobar.com")
    assert r.status_code == 200
