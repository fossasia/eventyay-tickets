import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.core.management import call_command

from venueless.routing import application


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
async def test_remote_disconnect():
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        await sync_to_async(call_command)("connections", "drop", "*")

        assert {"type": "websocket.close"} == await communicator.receive_output()
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
async def test_remote_reload():
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        await sync_to_async(call_command)("connections", "force_reload", "*")

        assert ["connection.reload", {}] == await communicator.receive_json_from()
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
async def test_remote_reload_staggered():
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        await sync_to_async(call_command)(
            "connections", "force_reload", "--interval", "20", "*"
        )

        assert ["connection.reload", {}] == await communicator.receive_json_from()
    finally:
        await communicator.disconnect()
