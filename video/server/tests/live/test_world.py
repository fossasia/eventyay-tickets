from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from tests.utils import get_token

from venueless.routing import application


@database_sync_to_async
def get_rooms(world):
    return list(world.rooms.all().prefetch_related("channel"))


@asynccontextmanager
async def world_communicator(token=None):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    if token:
        await communicator.send_json_to(["authenticate", {"token": token}])
        await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_rooms_unique_names(world):
    token = get_token(world, ["admin"])
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        await c.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await c.receive_json_from()

        await c.send_json_to(
            [
                "room.create",
                123,
                {
                    "name": "New Room!!",
                    "description": "a description",
                    "modules": [{"type": "chat.native"}],
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        await c.receive_json_from()

        await c.send_json_to(
            [
                "room.create",
                123,
                {
                    "name": "New Room!!",
                    "description": "a description",
                    "modules": [{"type": "chat.native"}],
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "error"


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("can_create_rooms", [True, False])
@pytest.mark.parametrize("with_channel", [True, False])
async def test_create_rooms(world, can_create_rooms, with_channel):
    token = get_token(world, ["admin" if can_create_rooms else "nope"])
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        await c.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await c.receive_json_from()

        rooms = await get_rooms(world)
        assert len(rooms) == 7

        modules = []
        if with_channel:
            modules.append({"type": "chat.native"})
        else:
            modules.append({"type": "weird.module"})
        await c.send_json_to(
            [
                "room.create",
                123,
                {
                    "name": "New Room!!",
                    "description": "a description",
                    "modules": modules,
                },
            ]
        )
        response = await c.receive_json_from()
        if with_channel and can_create_rooms:
            assert response[0] == "success"

            new_rooms = await get_rooms(world)
            assert len(new_rooms) == len(rooms) + 1

            assert response[-1]["room"]
            assert bool(response[-1]["channel"]) is with_channel
            second_response = await c.receive_json_from()
            assert second_response[0] == "room.create"
            assert response[-1]["room"] == second_response[-1]["id"]
        else:
            assert response[0] == "error"
            new_rooms = await get_rooms(world)
            assert len(new_rooms) == len(rooms)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_get(world):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(["world.config.get", 123, {}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        del response[2]["roles"]  # let this test break less often
        del response[2]["available_permissions"]  # let this test break less often
        assert response[2] == {
            "theme": {},
            "trait_grants": {
                "admin": ["admin"],
                "viewer": ["global-viewer"],
                "apiuser": ["api"],
                "speaker": ["speaker"],
                "attendee": [],
                "moderator": ["moderator"],
                "room_owner": ["room-owner"],
                "participant": ["global-participant"],
                "room_creator": ["room-creator"],
            },
            "bbb_defaults": {"record": False},
            "pretalx": {"base_url": "https://pretalx.com/democon/"},
            "title": "Unsere tolle Online-Konferenz",
            "locale": "en",
            "timezone": "Europe/Berlin",
            "connection_limit": 2,
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_patch(world):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(["world.config.patch", 123, {"title": "Foo"}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await database_sync_to_async(world.refresh_from_db)()
        assert world.title == "Foo"
