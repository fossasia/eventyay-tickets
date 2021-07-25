import pytest
from django.conf import settings


@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
def test_healthcheck_valid(client, world):
    r = client.get("/healthcheck/", HTTP_HOST="foobar.com")
    assert r.status_code == 200
