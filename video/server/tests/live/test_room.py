import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from django.test import override_settings

from tests.utils import LoggingCommunicator, get_token
from venueless.core.models import User
from venueless.routing import application


@asynccontextmanager
async def world_communicator(token=None, client_id=None):
    communicator = LoggingCommunicator(application, "/ws/world/sample/")
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
        await c.receive_json_from()  # world.user_count_change
        await c.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        await c.receive_json_from()  # world.user_count_change


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reactions_invalid(world, stream_room):
    async with world_communicator() as c1:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c1.receive_json_from()  # world.user_count_change

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👎"}]
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
        await c1.receive_json_from()  # world.user_count_change

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👍"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"👍": 1},
            "room": str(stream_room.pk),
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reactions_room_debounce(world, stream_room):
    async with world_communicator() as c1:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c1.receive_json_from()  # world.user_count_change

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👍"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👍"}]
        )

        # Order of responses is not deterministic
        responses = [
            await c1.receive_json_from(timeout=3),
            await c1.receive_json_from(timeout=3),
        ]
        assert any(
            r
            == [
                "room.reaction",
                {"reactions": {"👍": 1}, "room": str(stream_room.pk)},
            ]
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
        responses = [
            r[0] for r in (await c1.receive_json_from(), await c1.receive_json_from())
        ]
        assert "world.user_count_change" in responses
        assert "success" in responses
        await c2.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        responses = [
            r[0] for r in (await c2.receive_json_from(), await c2.receive_json_from())
        ]
        assert "world.user_count_change" in responses
        assert "success" in responses

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👍"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c2.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👍"}]
        )
        response = await c2.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"👍": 2},
            "room": str(stream_room.pk),
        }
        response = await c2.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"👍": 2},
            "room": str(stream_room.pk),
        }

        await asyncio.sleep(1.5)

        await c1.send_json_to(
            ["room.react", 123, {"room": str(stream_room.pk), "reaction": "👍"}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c2.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from(timeout=3)
        assert response[0] == "room.reaction"
        assert response[1] == {
            "reactions": {"👍": 1},
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
        assert len(response[2]) == 8


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_change_schedule_data_unauthorized(world, stream_room):
    async with world_communicator() as c1, world_communicator() as c2:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c1.receive_json_from()  # world.user_count_change

        await c2.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        responses = [
            r[0] for r in (await c2.receive_json_from(), await c2.receive_json_from())
        ]
        assert "world.user_count_change" in responses
        assert "success" in responses

        await c1.send_json_to(
            [
                "room.schedule",
                123,
                {"room": str(stream_room.pk), "data": {"session": 1}},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "error"  # Regular users cannot change schedule data
        assert response[2]["code"] == "protocol.denied"

        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()


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
                {"type": "question", "config": {"active": True}},
                {"type": "poll", "config": {"active": True}},
                {"type": "chat.native", "config": {"volatile": True}},
            ],
            "picture": None,
            "name": "Plenum",
            "force_join": False,
            "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
            "sorting_priority": 2,
            "pretalx_id": 130,
            "schedule_data": None,
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
async def test_config_reorder(world, chat_room, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(
            ["room.config.reorder", 123, [str(chat_room.pk), str(stream_room.pk)]]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        assert response[2][0]["name"] == "Chat"
        assert response[2][1]["name"] == "Plenum"
        await c1.send_json_to(
            ["room.config.reorder", 123, [str(stream_room.pk), str(chat_room.pk)]]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        assert response[2][0]["name"] == "Plenum"
        assert response[2][1]["name"] == "Chat"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_config_delete(world, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(["room.delete", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await database_sync_to_async(stream_room.refresh_from_db)()
        assert stream_room.deleted


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_change_schedule_data(world, stream_room):
    token = get_token(world, ["moderator"])
    async with world_communicator(token=token) as c1, world_communicator() as c2:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        await c1.receive_json_from()  # world.user_count_change

        await c2.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        await c1.receive_json_from()  # room.viewer.added

        responses = [
            r[0] for r in (await c2.receive_json_from(), await c2.receive_json_from())
        ]
        assert "world.user_count_change" in responses
        assert "success" in responses

        await c1.send_json_to(
            [
                "room.schedule",
                123,
                {"room": str(stream_room.pk), "schedule_data": {"session": 1}},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from()
        assert response[0] == "room.schedule"
        assert response[1] == {
            "room": str(stream_room.pk),
            "schedule_data": {"session": 1},
        }

        response = await c2.receive_json_from()
        assert response[0] == "room.schedule"
        assert response[1] == {
            "room": str(stream_room.pk),
            "schedule_data": {"session": 1},
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_user_count(world, stream_room):
    async with world_communicator() as c1, world_communicator() as c2:
        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        response = await c1.receive_json_from()
        assert response == [
            "world.user_count_change",
            {"room": str(stream_room.pk), "users": "few"},
        ]
        response = await c2.receive_json_from()
        assert response == [
            "world.user_count_change",
            {"room": str(stream_room.pk), "users": "few"},
        ]

        await c2.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"
        await c2.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"

        await c1.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        response = await c1.receive_json_from()
        assert response == [
            "world.user_count_change",
            {"room": str(stream_room.pk), "users": "none"},
        ]
        response = await c2.receive_json_from()
        assert response == [
            "world.user_count_change",
            {"room": str(stream_room.pk), "users": "none"},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_viewers(world, stream_room):
    token = get_token(world, ["moderator"], uid="moderator")

    async with world_communicator(token=token) as c1, world_communicator(
        client_id="guest"
    ) as c2, world_communicator(client_id="guest") as c3:
        u1 = await database_sync_to_async(User.objects.get)(token_id="moderator")
        u2 = await database_sync_to_async(User.objects.get)(client_id="guest")

        await c1.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        viewers = response[2]["viewers"]
        assert len(viewers) == 1
        assert str(viewers[0]["id"]) == str(u1.pk)

        await c1.receive_json_from()  # world.user_count_change
        await c2.receive_json_from()  # world.user_count_change
        await c3.receive_json_from()  # world.user_count_change

        await c2.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert "viewers" not in response[2]

        response = await c1.receive_json_from()  # room.viewer.added
        assert response[0] == "room.viewer.added"
        assert str(response[1]["user"]["id"]) == str(u2.pk)

        # same user joins with a different browser
        await c3.send_json_to(["room.enter", 123, {"room": str(stream_room.pk)}])
        response = await c3.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from()  # room.viewer.added
        assert response[0] == "room.viewer.added"
        assert str(response[1]["user"]["id"]) == str(u2.pk)

        # user leaves with first browser
        await c2.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c2.receive_json_from()
        assert response[0] == "success"

        # user leaves with second browser
        await c3.send_json_to(["room.leave", 123, {"room": str(stream_room.pk)}])
        response = await c3.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from()  # room.viewer.added
        assert response[0] == "room.viewer.removed"
        assert str(response[1]["user_id"]) == str(u2.pk)

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
@override_settings(SHORT_URL="https://vnls.io")
async def test_invite_anonymous_link(world, stream_room):
    async with world_communicator(token=get_token(world, ["admin"])) as c1:
        await c1.send_json_to(
            ["room.invite.anonymous.link", 123, {"room": str(stream_room.pk)}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        url = response[2]["url"]
        assert url.startswith("https://vnls.io/")

        await c1.send_json_to(
            ["room.invite.anonymous.link", 123, {"room": str(stream_room.pk)}]
        )
        response = await c1.receive_json_from()
        assert url == response[2]["url"]
