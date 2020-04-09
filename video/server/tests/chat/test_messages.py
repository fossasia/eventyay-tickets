import asyncio
from contextlib import asynccontextmanager

import pytest
from channels.testing import WebsocketCommunicator

from stayseated.routing import application


@asynccontextmanager
async def event_communicator():
    communicator = WebsocketCommunicator(application, "/ws/event/sample/")
    await communicator.connect()
    response = await communicator.receive_json_from()
    assert response[0] == "event.config"
    yield communicator
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_join_unknown_room():
    async with event_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"room": "room_unk"}])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"message": "Unknown room ID."}]


@pytest.mark.asyncio
async def test_join_room_without_chat():
    async with event_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"room": "room_1"}])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"message": "Room does not contain a chat."}]


@pytest.mark.asyncio
async def test_join_leave():
    async with event_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"room": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]
        await c.send_json_to(["chat.leave", 123, {"room": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]


@pytest.mark.asyncio
async def test_bogus_command():
    async with event_communicator() as c:
        await c.send_json_to(["chat.join", 123, {"room": "room_0"}])
        response = await c.receive_json_from()
        assert response == ["success", 123, {}]
        await c.send_json_to(["chat.lol", 123, ""])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"code": "chat.unsupported_command"}]


@pytest.mark.asyncio
async def test_send_message_to_other_client():
    async with event_communicator() as c1, event_communicator() as c2:
        await c1.send_json_to(["chat.join", 123, {"room": "room_0"}])
        response = await c1.receive_json_from()
        assert response == ["success", 123, {}]
        await c2.send_json_to(["chat.join", 123, {"room": "room_0"}])
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "room": "room_0",
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
                "room": "room_0",
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
                "room": "room_0",
                "event_type": "message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": "user_todo",
                "event_id": 0,
            },
        ]


@pytest.mark.asyncio
async def test_no_message_after_leave():
    async with event_communicator() as c1, event_communicator() as c2:
        await c1.send_json_to(["chat.join", 123, {"room": "room_0"}])
        response = await c1.receive_json_from()
        assert response == ["success", 123, {}]
        await c2.send_json_to(["chat.join", 123, {"room": "room_0"}])
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]
        await c2.send_json_to(["chat.leave", 123, {"room": "room_0"}])
        response = await c2.receive_json_from()
        assert response == ["success", 123, {}]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "room": "room_0",
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
                "room": "room_0",
                "event_type": "message",
                "content": {"type": "text", "body": "Hello world"},
                "sender": "user_todo",
                "event_id": 0,
            },
        ]

        with pytest.raises(asyncio.TimeoutError):
            response = await c2.receive_json_from()
