from contextlib import asynccontextmanager

import pytest
from channels.testing import WebsocketCommunicator

from stayseated.routing import application


@asynccontextmanager
async def world_communicator():
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    yield communicator
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ping_without_authentication():
    async with world_communicator() as c:
        await c.send_json_to(["ping", 1])
        response = await c.receive_json_from()
        assert response == ["pong", 1]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ping_with_authentication():
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        await c.send_json_to(["ping", 1])
        response = await c.receive_json_from()
        assert response == ["pong", 1]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unknown_component():
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        await c.send_json_to(["foo.bar", 1, 2])
        response = await c.receive_json_from()
        assert response == ["error", 1, {"code": "protocol.unknown_command"}]
