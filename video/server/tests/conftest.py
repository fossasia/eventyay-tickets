import datetime as dt
import json

import pytest
from channels.db import database_sync_to_async
from channels.layers import channel_layers, get_channel_layer
from django.conf import settings
from django.utils.timezone import now

from venueless.core.models import (
    BBBServer,
    Channel,
    ChatEvent,
    Exhibitor,
    Room,
    User,
    World,
)
from venueless.core.models.world import PlannedUsage


@pytest.fixture(autouse=True)
async def clear_redis():
    from venueless.core.utils.redis import aioredis

    if settings.REDIS_USE_PUBSUB:
        try:
            await get_channel_layer().flush()
        except:
            channel_layers._reset_backends("CHANNEL_LAYERS")

    async with aioredis() as redis:
        await redis.flushall()


@pytest.fixture(autouse=True)
async def bbb_server():
    await database_sync_to_async(BBBServer.objects.create)(
        url="https://video1.pretix.eu/bigbluebutton/", secret="bogussecret", active=True
    )


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
def bbb_room(rooms, bbb_server):  # pragma: no cover
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
def questions_room(rooms):
    for room in rooms:  # pragma: no cover
        if any(
            "question" == module["type"] and module["config"]["active"]
            for module in room.module_config
        ):
            return room


@pytest.fixture
def inactive_questions_room(rooms):
    for room in rooms:  # pragma: no cover
        if any(
            "question" == module["type"] and not module["config"].get("active")
            for module in room.module_config
        ):
            return room


@pytest.fixture
def unmoderated_questions_room(rooms):
    for room in rooms:  # pragma: no cover
        if any(
            "question" == module["type"]
            and not module["config"].get("requires_moderation", True)
            for module in room.module_config
        ):
            return room


@pytest.fixture
def stream_room(rooms):
    for room in rooms:  # pragma: no cover
        if any("livestream.native" == module["type"] for module in room.module_config):
            return room


@pytest.fixture
def exhibition_room(rooms):
    for room in rooms:  # pragma: no cover
        if any("exhibition.native" == module["type"] for module in room.module_config):
            return room


@database_sync_to_async
def _clear_db():
    ChatEvent.objects.all().delete()
    Channel.objects.all().delete()
    User.objects.all().delete()
    Room.objects.all().delete()
    Exhibitor.objects.all().delete()
    World.objects.all().delete()


@pytest.fixture(autouse=True)
@pytest.mark.django_db
async def clear_database(request):
    if "django_db" not in request.keywords:  # pragma: no cover
        return
    await _clear_db()


@pytest.fixture
def staff_user():
    from django.contrib.auth.models import User

    return User.objects.create(is_staff=True)


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def planned_usage(world_data):
    from venueless.core.utils.config import import_config

    import_config(world_data)
    world = World.objects.all().get()
    world.domain = "localhost"
    world.save()
    return PlannedUsage.objects.create(
        world=world,
        start=now() + dt.timedelta(days=10),
        end=now() + dt.timedelta(days=13),
        attendees=200,
    )
