import pytest
from channels.db import database_sync_to_async

from stayseated.core.models import ChatEvent, User


@pytest.fixture(autouse=True)
async def clear_redis():
    from stayseated.core.utils.redis import aioredis

    async with aioredis() as redis:
        await redis.flushall()


@database_sync_to_async
def _clear_db():
    ChatEvent.objects.all().delete()
    User.objects.all().delete()


@pytest.fixture(autouse=True)
@pytest.mark.django_db
async def clear_database(request):
    if "django_db" not in request.keywords:
        return
    await _clear_db()
