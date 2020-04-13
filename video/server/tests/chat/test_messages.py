import asyncio
from contextlib import asynccontextmanager

import pytest
from channels.testing import WebsocketCommunicator

from stayseated.routing import application


@asynccontextmanager
async def event_communicator(named=True):
    communicator = WebsocketCommunicator(application, "/ws/event/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": 4}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    assert "event.config" in response[1], response
    if named:
        await communicator.send_json_to(
            ["user.update", 123, {"public_name": "Foo Fighter"}]
        )
        await communicator.receive_json_from()
    yield communicator
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_join_unknown_event():
    communicator = WebsocketCommunicator(application, "/ws/event/sampleeeeeeee/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": 4}])
    response = await communicator.receive_json_from()
    assert response == ["error", {"code": "event.unknown_event"}]


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("action", ("join", "subscribe"))
async def test_join_or_subscribe_unknown_room(action):
    async with event_communicator() as c:
        await c.send_json_to([f"chat.{action}", 123, {"channel": "room_unk"}])
        response = await c.receive_json_from()
        assert response == [
            "error",
            123,
            {"message": "Unknown room ID", "code": "room.unknown"},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("action", ("join", "subscribe"))
async def test_join_or_subscribe_room_without_chat(action):
    async with event_communicator() as c:
        await c.send_json_to([f"chat.{action}", 123, {"channel": "room_1"}])
        response = await c.receive_json_from()
        assert response == [
            "error",
            123,
            {"message": "Room does not contain a chat.", "code": "chat.unknown"},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_leave():
    async with event_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c.send_json_to(["chat.leave", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_join_without_name():
    async with event_communicator(named=False) as c:
        await c.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"code": "channel.join.missing_name"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscribe_without_name():
    async with event_communicator(named=False) as c:
        await c.send_json_to(["chat.subscribe", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscribe_join_leave():
    async with event_communicator() as c:
        await c.send_json_to(["chat.subscribe", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c.send_json_to(["chat.leave", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]
        await c.send_json_to(["chat.unsubscribe", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bogus_command():
    async with event_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c.send_json_to(["chat.lol", 123, ""])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"code": "chat.unsupported_command"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_message_to_other_client():
    async with event_communicator() as c1, event_communicator() as c2:
        await c1.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c1.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c2.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert response[2]["state"] is None
        assert len(response[2]["members"]) == 1
        assert list(response[2]["members"][0].keys()) == ["user_id", "public_name"]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": "room_0",
                    "event_type": "message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == ["success", 123, {}]

        response = await c1.receive_json_from()
        response[1]["event_id"] = 0
        assert response == [
            "chat.event",
            {
                "channel": "room_0",
                "event_type": "message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": "user_todo",
                "event_id": 0,
            },
        ]

        response = await c2.receive_json_from()
        response[1]["event_id"] = 0
        assert response == [
            "chat.event",
            {
                "channel": "room_0",
                "event_type": "message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": "user_todo",
                "event_id": 0,
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_still_messages_after_leave():
    async with event_communicator() as c1, event_communicator() as c2:
        await c1.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c1.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c2.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert response[2]["state"] is None
        assert len(response[2]["members"]) == 1
        assert list(response[2]["members"][0].keys()) == ["user_id", "public_name"]
        await c2.send_json_to(["chat.leave", 123, {"channel": "room_0"}])
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": "room_0",
                    "event_type": "message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == ["success", 123, {}]

        response = await c1.receive_json_from()
        response[1]["event_id"] = 0
        assert response == [
            "chat.event",
            {
                "channel": "room_0",
                "event_type": "message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": "user_todo",
                "event_id": 0,
            },
        ]
        response = await c2.receive_json_from()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_message_after_unsubscribe():
    async with event_communicator() as c1, event_communicator() as c2:
        await c1.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c1.receive_json_from()
        assert response == ["success", 123, {"state": None, "members": []}]
        await c2.send_json_to(["chat.join", 123, {"channel": "room_0"}])
        response = await c2.receive_json_from()
        assert response[0] == "success"
        assert response[2]["state"] is None
        assert len(response[2]["members"]) == 1
        assert list(response[2]["members"][0].keys()) == ["user_id", "public_name"]
        await c2.send_json_to(["chat.unsubscribe", 123, {"channel": "room_0"}])
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": "room_0",
                    "event_type": "message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c1.receive_json_from()
        assert response == ["success", 123, {}]

        response = await c1.receive_json_from()
        response[1]["event_id"] = 0
        assert response == [
            "chat.event",
            {
                "channel": "room_0",
                "event_type": "message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": "user_todo",
                "event_id": 0,
            },
        ]

        with pytest.raises(asyncio.TimeoutError):
            response = await c2.receive_json_from()
