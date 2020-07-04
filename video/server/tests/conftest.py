import json

import pytest
from channels.db import database_sync_to_async

from venueless.core.models import Channel, ChatEvent, Room, User, World


@pytest.fixture(autouse=True)
async def clear_redis():
    from venueless.core.utils.redis import aioredis

    async with aioredis() as redis:
        await redis.flushall()


@pytest.fixture(scope="session")
def world_data():
    with open("sample/worlds/sample.json") as f:
        world_data = json.load(f)
    return world_data


@database_sync_to_async
def _import_world(world_data):
    from venueless.core.utils.config import import_config

    import_config(world_data)
    world = World.objects.all().get()
    world.domain = "localhost"
    world.save()
    return world


@pytest.fixture(autouse=True)
async def world(world_data):
    world = await _import_world(world_data)
    return world


@database_sync_to_async
def _get_rooms(world):
    return list(world.rooms.all().prefetch_related("channel"))


@pytest.fixture
async def rooms(world):
    rooms = await _get_rooms(world)
    return rooms


@pytest.fixture
def bbb_room(rooms):  # pragma: no cover
    for room in rooms:
        if any("call.bigbluebutton" == module["type"] for module in room.module_config):
            return room


@pytest.fixture
def volatile_chat_room(rooms):
    for room in rooms:  # pragma: no cover
        if any(
            "chat.native" == module["type"] and module["config"]["volatile"] is True
            for module in room.module_config
        ):
            return room


@pytest.fixture
def chat_room(rooms):
    for room in rooms:  # pragma: no cover
        if any(
            "chat.native" == module["type"] and module["config"]["volatile"] is False
            for module in room.module_config
        ):
            return room


@pytest.fixture
def stream_room(rooms):
    for room in rooms:  # pragma: no cover
        if any("livestream.native" == module["type"] for module in room.module_config):
            return room


@database_sync_to_async
def _clear_db():
    ChatEvent.objects.all().delete()
    Channel.objects.all().delete()
    User.objects.all().delete()
    Room.objects.all().delete()
    World.objects.all().delete()


@pytest.fixture(autouse=True)
@pytest.mark.django_db
async def clear_database(request):
    if "django_db" not in request.keywords:  # pragma: no cover
        return
    await _clear_db()
