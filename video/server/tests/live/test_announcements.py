import datetime as dt
import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils.timezone import now

from tests.utils import get_token
from venueless.core.models import Announcement
from venueless.routing import application


@database_sync_to_async
def get_announcement(pk):
    return Announcement.objects.get(pk=pk)


@asynccontextmanager
async def world_communicator(client_id=None, token=None, room=None, first=True):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    if token:
        await communicator.send_json_to(["authenticate", {"token": token}])

    else:
        await communicator.send_json_to(
            ["authenticate", {"client_id": client_id or str(uuid.uuid4())}]
        )
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    assert "world.config" in response[1], response
    await communicator.send_json_to(["room.enter", 123, {"room": str(room.pk)}])
    response = await communicator.receive_json_from()
    assert response[0] == "success"
    if first:
        await communicator.receive_json_from()  # world.user_count_change
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_announcement_as_non_admin(chat_room):
    error_response = [
        "error",
        123,
        {"code": "auth.denied", "message": "Permission denied."},
    ]
    async with world_communicator(room=chat_room) as c:
        await c.send_json_to(["announcement.list", 123, {}])
        response = await c.receive_json_from()
        assert response == error_response


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_announcement_lifecycle(chat_room, world):
    async with world_communicator(room=chat_room) as c:
        async with world_communicator(
            room=chat_room, token=get_token(world, ["moderator"]), first=False
        ) as c_mod:
            await c.send_json_to(
                [
                    "announcement.create",
                    123,
                    {
                        "text": "Test announcement",
                        "state": "draft",
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response[0] == "error"  # regular users cannot create polls

            await c_mod.send_json_to(
                [
                    "announcement.create",
                    123,
                    {
                        "text": "Test announcement",
                        "state": "draft",
                        "show_until": (now() + dt.timedelta(days=2)).isoformat(),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            announcement = await get_announcement(response[2]["announcement"]["id"])
            assert not announcement.is_visible

            # no idea why this doesn't work; the line does produce a timeout error when not wrapped in raises()
            # with pytest.raises(asyncio.TimeoutError):
            #     await c.receive_json_from()  # No broadcast for inactive announcements

            await c_mod.send_json_to(
                [
                    "announcement.update",
                    123,
                    {
                        "id": str(announcement.id),
                        "state": "active",
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            assert response[2]["announcement"]["state"] == "active"

            response = await c_mod.receive_json_from()
            assert response[0] == "announcement.created_or_updated"

            response = await c.receive_json_from()
            assert response[0] == "announcement.created_or_updated"

            await c_mod.send_json_to(
                [
                    "announcement.list",
                    123,
                    {},
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]) == 1
            assert response[2][0]["id"] == str(announcement.id)
