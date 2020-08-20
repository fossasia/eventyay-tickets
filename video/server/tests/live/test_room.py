import asyncio
import uuid
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
        await communicator.send_json_to(
            ["authenticate", {"client_id": str(uuid.uuid4())}]
        )
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    assert "world.config" in response[1], response
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_enter_leave_room(world, stream_room):
    async with world_communicator() as c:
        await c.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        await c.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reactions_invalid(world, stream_room):
    async with world_communicator() as c1:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "hate"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "error"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reactions_room(world, stream_room):
    async with world_communicator() as c1:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "+1"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"+1": 1},
            "room": str(stream_room.pk),
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reactions_room_debounce(world, stream_room):
    async with world_communicator() as c1:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "+1"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "+1"}]
        )

        # Order of responses is not deterministic
        responses = [
            await c1.receive_json_from(timeout=3),
            await c1.receive_json_from(timeout=3),
        ]
        assert any(
            r
            == ["room.reaction", {"reactions": {"+1": 1}, "room": str(stream_room.pk)},]
            for r in responses
        )
        assert any(r == ["success", 123, {}] for r in responses)

        # Responses are drained
        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reactions_room_aggregate(world, stream_room):
    async with world_communicator() as c1, world_communicator() as c2:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c2.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "+1"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c2.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "+1"}]
        )
        response = await c2.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"+1": 2},
            "room": str(stream_room.pk),
        }
        response = await c2.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"+1": 2},
            "room": str(stream_room.pk),
        }

        await asyncio.sleep(1.5)

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "+1"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c2.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"+1": 1},
            "room": str(stream_room.pk),
        }
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_list(world, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(["room.config.list", 123, {}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        assert len(response[2]) == 7


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_get(world, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(["room.config.get", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        assert response[2] == {
            "id": str(stream_room.pk),
            "trait_grants": {"viewer": [], "participant": []},
            "module_config": [
                {
                    "type": "livestream.native",
                    "config": {"hls_url": "https://s1.live.pretix.eu/hls/sample.m3u8"},
                },
                {"type": "chat.native", "config": {"volatile": True}},
            ],
            "picture": None,
            "name": "Plenum",
            "force_join": False,
            "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
            "sorting_priority": 2,
            "pretalx_id": 130,
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_patch(world, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(
            ["room.config.patch", 123, {"room": str(stream_room.pk), "name": "Foo"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await database_sync_to_async(stream_room.refresh_from_db)()
        assert stream_room.name == "Foo"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_delete(world, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(["room.delete", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await database_sync_to_async(stream_room.refresh_from_db)()
        assert stream_room.deleted
