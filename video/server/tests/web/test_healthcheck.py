import pytest


@pytest.mark.django_db
def test_healthcheck_valid(client, world):
    r = client.get("/healthcheck/", HTTP_HOST="foobar.com")
    assert r.status_code == 200
