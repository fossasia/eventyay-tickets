import asyncio
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from tests.utils import get_token

from venueless.routing import application


@asynccontextmanager
async def world_communicator(token=None):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    if token:
        await communicator.send_json_to(["authenticate", {"token": token}])
    else:
        await communicator.send_json_to(["authenticate", {"client_id": 4}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated"
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_limit_missing(world):
    world.config["connection_limit"] = None
    await database_sync_to_async(world.save)()
    async with world_communicator() as c1, world_communicator() as c2, world_communicator() as c3:
        await c1.send_json_to(["ping", 1])
        response = await c1.receive_json_from()
        assert response == ["pong", 1]
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()
        with pytest.raises(asyncio.TimeoutError):
            await c3.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_limit_1(world):
    world.config["connection_limit"] = 1
    await database_sync_to_async(world.save)()
    async with world_communicator() as c1, world_communicator() as c2, world_communicator() as c3:
        response = await c1.receive_json_from()
        assert response == [
            "error",
            {"code": "connection.replaced", "message": "Connection replaced"},
        ]
        response = await c2.receive_json_from()
        assert response == [
            "error",
            {"code": "connection.replaced", "message": "Connection replaced"},
        ]
        await asyncio.sleep(0.5)
        await c3.send_json_to(["ping", 1])
        response = await c3.receive_json_from()
        assert response == ["pong", 1]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_limit_2(world):
    world.config["connection_limit"] = 2
    await database_sync_to_async(world.save)()
    async with world_communicator() as c1, world_communicator() as c2, world_communicator() as c3:
        response = await c1.receive_json_from()
        assert response == [
            "error",
            {"code": "connection.replaced", "message": "Connection replaced"},
        ]
        await asyncio.sleep(0.5)
        await c2.send_json_to(["ping", 1])
        response = await c2.receive_json_from()
        assert response == ["pong", 1]
        await c3.send_json_to(["ping", 1])
        response = await c3.receive_json_from()
        assert response == ["pong", 1]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unlimited_admin(world):
    world.config["connection_limit"] = 1
    await database_sync_to_async(world.save)()
    t = get_token(world, ["admin"])
    async with world_communicator(token=t) as c1, world_communicator(
        token=t
    ) as c2, world_communicator(token=t) as c3:
        await c1.send_json_to(["ping", 1])
        response = await c1.receive_json_from()
        assert response == ["pong", 1]
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()
        with pytest.raises(asyncio.TimeoutError):
            await c3.receive_json_from()
