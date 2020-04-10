from contextlib import asynccontextmanager
import pytest

from channels.testing import WebsocketCommunicator

from stayseated.routing import application


@asynccontextmanager
async def event_communicator():
    communicator = WebsocketCommunicator(application, "/ws/event/sample/")
    await communicator.connect()
    yield communicator
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_without_token():
    async with event_communicator() as c, event_communicator() as c2:
        await c.send_json_to(["authenticate", {}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"event.config", "user.config"}
