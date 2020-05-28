import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from tests.utils import get_token

from venueless.core.services.chat import ChatService
from venueless.core.utils.redis import aioredis
from venueless.routing import application


@asynccontextmanager
async def world_communicator(client_id=None, named=True, token=None):
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
    if named:
        await communicator.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_unknown_event():
    communicator = WebsocketCommunicator(application, "/ws/world/sampleeeeeeee/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response == ["error", {"code": "world.unknown_world"}]


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("action", ("join", "subscribe"))
async def test_join_or_subscribe_unknown_room(action):
    async with world_communicator() as c:
        await c.send_json_to([f"chat.{action}", 123, {"channel": "room_unk"}])
        response = await c.receive_json_from()
        assert response == [
            "error",
            123,
            {"message": "Unknown room ID", "code": "room.unknown"},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_leave(chat_room):
    async with world_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"channel": str(chat_room.channel.id)}])
        response = await c.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        response = await c.receive_json_from()
        del response[1]["timestamp"]
        assert response == [
            "chat.event",
            {
                "channel": str(chat_room.channel.id),
                "event_id": 1,
                "event_type": "channel.member",
                "sender": c.context["user.config"]["id"],
                "edited": None,
                "replaces": None,
                "content": {
                    "membership": "join",
                    "user": {
                        "profile": {"display_name": "Foo Fighter"},
                        "id": c.context["user.config"]["id"],
                    },
                },
            },
        ]

        await c.send_json_to(
            ["chat.leave", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_volatile_based_on_room_config(volatile_chat_room, chat_room):
    cid = str(uuid.uuid4())
    async with world_communicator(client_id=cid) as c, world_communicator(
        client_id=cid, named=False
    ) as c2:
        await c.send_json_to(
            ["chat.join", 123, {"channel": str(volatile_chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        response = await c.receive_json_from()
        assert response[0] == "chat.event"

        assert await ChatService("sample").membership_is_volatile(
            str(volatile_chat_room.channel.id), c.context["user.config"]["id"]
        )

        response = await c2.receive_json_from()
        assert response == ["chat.channels", {"channels": []}]

        await c.send_json_to(["chat.join", 123, {"channel": str(chat_room.channel.id)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        response = await c.receive_json_from()
        assert response[0] == "chat.event"

        assert not await ChatService("sample").membership_is_volatile(
            str(chat_room.channel.id), c.context["user.config"]["id"]
        )

        response = await c2.receive_json_from()
        assert response == [
            "chat.channels",
            {"channels": [str(chat_room.channel.id)]},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_convert_volatile_to_persistent(volatile_chat_room):
    async with world_communicator() as c:
        volatile_chat_room.trait_grants["moderator"] = []
        await database_sync_to_async(volatile_chat_room.save)()
        await c.send_json_to(
            ["chat.join", 123, {"channel": str(volatile_chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        response = await c.receive_json_from()
        assert response[0] == "chat.event"

        assert await ChatService("sample").membership_is_volatile(
            str(volatile_chat_room.channel.id), c.context["user.config"]["id"]
        )

        await c.send_json_to(
            [
                "chat.join",
                123,
                {"channel": str(volatile_chat_room.channel.id), "volatile": False},
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"

        assert not await ChatService("sample").membership_is_volatile(
            str(volatile_chat_room.channel.id), c.context["user.config"]["id"]
        )


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_convert_volatile_to_persistent_require_moderator(
    volatile_chat_room,
):
    async with world_communicator() as c:
        await c.send_json_to(
            ["chat.join", 123, {"channel": str(volatile_chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        response = await c.receive_json_from()
        assert response[0] == "chat.event"

        assert await ChatService("sample").membership_is_volatile(
            str(volatile_chat_room.channel.id), c.context["user.config"]["id"]
        )

        await c.send_json_to(
            [
                "chat.join",
                123,
                {"channel": str(volatile_chat_room.channel.id), "volatile": False},
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"

        assert await ChatService("sample").membership_is_volatile(
            str(volatile_chat_room.channel.id), c.context["user.config"]["id"]
        )


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_without_name(chat_room):
    async with world_communicator(named=False) as c:
        await c.send_json_to(["chat.join", 123, {"channel": str(chat_room.channel.id)}])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"code": "channel.join.missing_profile"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscribe_without_name(chat_room):
    async with world_communicator(named=False) as c:
        await c.send_json_to(
            ["chat.subscribe", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscribe_permission_denied(chat_room):
    chat_room.trait_grants = {}
    await database_sync_to_async(chat_room.save)()
    async with world_communicator(named=True) as c:
        await c.send_json_to(
            ["chat.subscribe", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        assert response == [
            "error",
            123,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscribe_join_leave(chat_room):
    async with world_communicator() as c:
        await c.send_json_to(
            ["chat.subscribe", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        await c.send_json_to(["chat.join", 123, {"channel": str(chat_room.channel.id)}])
        response = await c.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        response = await c.receive_json_from()
        del response[1]["timestamp"]
        assert response == [
            "chat.event",
            {
                "channel": str(chat_room.channel.id),
                "event_id": 1,
                "event_type": "channel.member",
                "edited": None,
                "replaces": None,
                "content": {
                    "membership": "join",
                    "user": {
                        "profile": {"display_name": "Foo Fighter"},
                        "id": c.context["user.config"]["id"],
                    },
                },
                "sender": c.context["user.config"]["id"],
            },
        ]
        await c.send_json_to(
            ["chat.leave", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bogus_command(chat_room):
    async with world_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"channel": str(chat_room.channel.id)}])
        response = await c.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        await c.receive_json_from()  # join notification
        await c.send_json_to(["chat.lol", 123, {}])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"code": "chat.unsupported_command"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unsupported_event_type(chat_room):
    async with world_communicator() as c1:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        await c1.receive_json_from()
        await c1.receive_json_from()
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "bogus",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == ["error", 123, {"code": "chat.unsupported_event_type"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unsupported_content_type(chat_room):
    async with world_communicator() as c1:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        await c1.receive_json_from()
        await c1.receive_json_from()
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "bogus", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == ["error", 123, {"code": "chat.unsupported_content_type"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_requires_membership(chat_room):
    async with world_communicator() as c1:
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == ["error", 123, {"code": "chat.denied"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_autofix_numbers(chat_room):
    async with world_communicator() as c1, aioredis() as redis:
        await redis.delete("chat.event_id")
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        await c1.receive_json_from()
        response = await c1.receive_json_from()
        assert response[1]["event_id"] == 1
        await redis.delete("chat.event_id")
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        await c1.receive_json_from()
        response = await c1.receive_json_from()
        assert response[1]["event_id"] == 3


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_private_room_protection(chat_room):
    chat_room.trait_grants = {}
    await database_sync_to_async(chat_room.save)()
    async with world_communicator() as c1:
        await c1.send_json_to(
            [
                "chat.fetch",
                123,
                {"channel": str(chat_room.channel.id), "count": 20, "before_id": 0,},
            ]
        )
        response = await c1.receive_json_from()
        assert response == [
            "error",
            123,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_read_only_room_protection(chat_room):
    chat_room.trait_grants = {"viewer": []}
    await database_sync_to_async(chat_room.save)()
    async with world_communicator() as c1:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c1.receive_json_from()
        assert response == [
            "error",
            123,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == [
            "error",
            123,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_fetch_messages_after_join(chat_room):
    async with world_communicator() as c1:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c1.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        await c1.receive_json_from()  # join notification c1

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        async with world_communicator() as c2:
            await c2.send_json_to(
                ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
            )
            response = await c2.receive_json_from()
            assert response[0] == "success"
            next_id = response[2]["next_event_id"]
            await c2.receive_json_from()  # join notification c2

            await c2.send_json_to(
                [
                    "chat.fetch",
                    123,
                    {
                        "channel": str(chat_room.channel.id),
                        "count": 20,
                        "before_id": next_id,
                    },
                ]
            )
            response = await c2.receive_json_from()
            assert len(response[2]["results"]) == 2
            del response[2]["results"][0]["timestamp"]
            del response[2]["results"][0]["event_id"]
            assert response[2]["results"][0] == {
                "channel": str(chat_room.channel.id),
                "event_type": "channel.member",
                "type": "chat.event",
                "edited": None,
                "replaces": None,
                "content": {
                    "user": {
                        "id": c1.context["user.config"]["id"],
                        "profile": {"display_name": "Foo Fighter"},
                    },
                    "membership": "join",
                },
                "sender": c1.context["user.config"]["id"],
            }
            del response[2]["results"][1]["timestamp"]
            del response[2]["results"][1]["event_id"]
            assert response[2]["results"][1] == {
                "channel": str(chat_room.channel.id),
                "type": "chat.event",
                "event_type": "channel.message",
                "edited": None,
                "replaces": None,
                "content": {"type": "text", "body": "Hello world"},
                "sender": c1.context["user.config"]["id"],
            }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_message_to_other_client(chat_room):
    async with world_communicator() as c1, world_communicator() as c2:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c1.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        await c1.receive_json_from()  # join notification c1
        await c2.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert response[2]["state"] is None
        assert len(response[2]["members"]) == 1
        assert list(response[2]["members"][0].keys()) == ["id", "profile"]
        response = await c1.receive_json_from()
        assert response[0] == "chat.event"
        assert response[1]["content"]["membership"] == "join"
        assert response[1]["content"]["user"]["id"] == c2.context["user.config"]["id"]
        await c2.receive_json_from()  # join notification c2

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        assert response[2]["event"]["event_type"] == "channel.message"
        assert response[2]["event"]["event_id"]

        response = await c1.receive_json_from()
        response[1]["event_id"] = 0
        del response[1]["timestamp"]
        assert response == [
            "chat.event",
            {
                "channel": str(chat_room.channel.id),
                "event_type": "channel.message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": c1.context["user.config"]["id"],
                "edited": None,
                "replaces": None,
                "event_id": 0,
            },
        ]

        response = await c2.receive_json_from()
        response[1]["event_id"] = 0
        del response[1]["timestamp"]
        assert response == [
            "chat.event",
            {
                "channel": str(chat_room.channel.id),
                "event_type": "channel.message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": c1.context["user.config"]["id"],
                "edited": None,
                "replaces": None,
                "event_id": 0,
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_messages_after_leave(chat_room):
    async with world_communicator() as c1, world_communicator() as c2:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c1.receive_json_from()
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        await c1.receive_json_from()  # join notification c1
        await c2.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert response[2]["state"] is None
        assert len(response[2]["members"]) == 1
        assert list(response[2]["members"][0].keys()) == ["id", "profile"]
        await c1.receive_json_from()  # join notification c1
        await c2.receive_json_from()  # join notification c2

        await c2.send_json_to(
            ["chat.leave", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()  # leave notification c2
        response = await c1.receive_json_from()  # leave notification c1
        assert response[0] == "chat.event"
        assert response[1]["content"]["membership"] == "leave"

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from()
        response[1]["event_id"] = 0
        del response[1]["timestamp"]
        assert response == [
            "chat.event",
            {
                "channel": str(chat_room.channel.id),
                "event_type": "channel.message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": c1.context["user.config"]["id"],
                "event_id": 0,
                "edited": None,
                "replaces": None,
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_message_after_unsubscribe(chat_room):
    async with world_communicator() as c1, world_communicator() as c2:
        await c1.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c1.receive_json_from()
        await c1.receive_json_from()  # join notification c1
        response[2]["next_event_id"] = -1
        assert response == [
            "success",
            123,
            {"state": None, "next_event_id": -1, "members": []},
        ]
        await c2.send_json_to(
            ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert response[2]["state"] is None
        assert len(response[2]["members"]) == 1
        assert list(response[2]["members"][0].keys()) == ["id", "profile"]
        await c1.receive_json_from()  # join notification c2
        await c2.receive_json_from()  # join notification c2

        await c2.send_json_to(
            ["chat.unsubscribe", 123, {"channel": str(chat_room.channel.id)}]
        )
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c1.receive_json_from()
        response[1]["event_id"] = 0
        del response[1]["timestamp"]
        assert response == [
            "chat.event",
            {
                "channel": str(chat_room.channel.id),
                "event_type": "channel.message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": c1.context["user.config"]["id"],
                "event_id": 0,
                "edited": None,
                "replaces": None,
            },
        ]

        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_disconnect_is_no_leave(chat_room):
    async with world_communicator(client_id=str(uuid.uuid4())) as c1:
        async with world_communicator(client_id=str(uuid.uuid4())) as c2:
            await c1.send_json_to(
                ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
            )
            response = await c1.receive_json_from()
            await c1.receive_json_from()  # join notification c1
            assert response == [
                "success",
                123,
                {"state": None, "members": [], "next_event_id": 1},
            ]
            await c2.send_json_to(
                ["chat.join", 123, {"channel": str(chat_room.channel.id)}]
            )
            response = await c2.receive_json_from()
            assert response[0] == "success"
            assert response[2]["state"] is None
            assert len(response[2]["members"]) == 1
            assert list(response[2]["members"][0].keys()) == ["id", "profile"]
            await c1.receive_json_from()  # join notification c2
            await c2.receive_json_from()  # join notification c2

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_last_disconnect_is_leave_in_volatile_channel(volatile_chat_room):
    client_id = str(uuid.uuid4())
    async with world_communicator() as c1:
        async with world_communicator(client_id=client_id) as c2:
            async with world_communicator(client_id=client_id, named=False) as c3:
                await c1.send_json_to(
                    ["chat.join", 123, {"channel": str(volatile_chat_room.channel.id)}]
                )
                response = await c1.receive_json_from()
                await c1.receive_json_from()  # join notification c1
                assert response == [
                    "success",
                    123,
                    {"state": None, "members": [], "next_event_id": 1},
                ]

                await c2.send_json_to(
                    ["chat.join", 124, {"channel": str(volatile_chat_room.channel.id)}]
                )
                response = await c2.receive_json_from()
                assert response[0] == "success"
                assert response[2]["state"] is None
                assert len(response[2]["members"]) == 1
                assert list(response[2]["members"][0].keys()) == ["id", "profile"]
                await c1.receive_json_from()  # join notification c2
                await c2.receive_json_from()  # join notification c2

                response = await c3.receive_json_from()
                assert response == ["chat.channels", {"channels": []}]

                await c3.send_json_to(
                    ["chat.join", 125, {"channel": str(volatile_chat_room.channel.id)}]
                )
                response = await c3.receive_json_from()
                assert response[0] == "success"
                # no join notification, was already in channel

                assert (
                    len(
                        await ChatService("sample").get_channel_users(
                            str(volatile_chat_room.channel.id)
                        )
                    )
                    == 2
                )
            assert (
                len(
                    await ChatService("sample").get_channel_users(
                        str(volatile_chat_room.channel.id)
                    )
                )
                == 2
            )
        assert (
            len(
                await ChatService("sample").get_channel_users(
                    str(volatile_chat_room.channel.id)
                )
            )
            == 1
        )

        response = await c1.receive_json_from()
        assert response[0] == "chat.event"
        assert response[1]["content"]["membership"] == "leave"

    assert (
        len(
            await ChatService("sample").get_channel_users(
                str(volatile_chat_room.channel.id)
            )
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize(
    "editor,editee,message_type,success",
    (
        ("user", "user", "text", True),
        ("user", "user", "deleted", True),
        ("user", "admin", "text", False),
        ("user", "admin", "deleted", False),
        ("admin", "user", "text", False),
        ("admin", "user", "deleted", True),
        ("admin", "admin", "text", True),
        ("admin", "admin", "deleted", True),
    ),
)
async def test_edit_messages(world, chat_room, editor, editee, message_type, success):
    editor_token = get_token(world, [editor])
    editee_token = get_token(world, [editee]) if editor != editee else None
    channel_id = str(chat_room.channel.id)
    async with world_communicator(token=editor_token) as c1, world_communicator(
        token=editee_token
    ) as c2:
        # Setup
        await c1.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c1.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c1
        await c2.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c2.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c2
        await c2.receive_json_from()  # Join notification c2

        edit_self = editor == editee
        editor, not_editor = c1, c2
        editee, not_editee = (c1, c2) if edit_self else (c2, c1)

        await editee.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await editee.receive_json_from()  # success
        await editee.receive_json_from()  # receives message
        await not_editee.receive_json_from()  # receives message

        event_id = response[2]["event"]["event_id"]
        content = (
            {"type": "text", "body": "Goodbye world"}
            if message_type == "text"
            else {"type": "deleted"}
        )

        await editor.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "replaces": event_id,
                    "content": content,
                },
            ]
        )
        response = await editor.receive_json_from()  # success

        if success:
            assert response[0] == "success"
            assert response[2]["event"]["event_type"] == "channel.message"
            assert response[2]["event"]["content"] == content
            assert response[2]["event"]["replaces"] == event_id
            await editor.receive_json_from()  # broadcast
            response = await not_editor.receive_json_from()  # broadcast
            assert response[0] == "chat.event"
            assert response[1]["event_type"] == "channel.message"
            assert response[1]["content"] == content
            assert response[1]["replaces"] == event_id
        else:
            assert response[0] == "error"
            assert response[2]["code"] == "chat.denied"
            with pytest.raises(asyncio.TimeoutError):
                await editor.receive_json_from()  # no message to either client
            with pytest.raises(asyncio.TimeoutError):
                await not_editor.receive_json_from()  # no message to either client
