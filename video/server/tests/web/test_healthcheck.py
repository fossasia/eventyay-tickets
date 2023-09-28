import pytest
from django.conf import settings


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
async def test_healthcheck_valid(async_client, world):
    r = await async_client.get("/healthcheck/", HTTP_HOST="foobar.com")
    assert r.status_code == 200
