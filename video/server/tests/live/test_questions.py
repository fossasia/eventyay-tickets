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
async def world_communicator(client_id=None, token=None, room=None):
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
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ask_question_when_not_active(inactive_questions_room):
    questions_room = inactive_questions_room
    async with world_communicator(room=inactive_questions_room) as c:
        await c.send_json_to(
            [
                "question.ask",
                123,
                {
                    "room": str(questions_room.id),
                    "content": "What is your favourite colour?",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response == [
            "error",
            123,
            {
                "code": "question.inactive",
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ask_question(questions_room, world):
    async with world_communicator(room=questions_room) as c:
        async with world_communicator(room=questions_room, token=get_token(world, ["moderator"])) as c_mod:
            await c.send_json_to(
                [
                    "question.ask",
                    123,
                    {
                        "room": str(questions_room.id),
                        "content": "What is your favourite colour?",
                    },
                ]
            )
            response = await c.receive_json_from()
            question_id = response[2]["question"]["id"]
            response[2]["question"]["id"] = -1
            response[2]["question"]["timestamp"] = -1
            assert response == [
                "success",
                123,
                {
                    "question": {
                        "answered": False,
                        "content": "What is your favourite colour?",
                        "id": -1,
                        "room_id": str(questions_room.id),
                        "state": "mod_queue",
                        "timestamp": -1,
                    }
                },
            ]
            await c.send_json_to(
                [
                    "question.update",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                        "content": "Where is your favourite colour?",
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response == [
                "error",
                {'code': 'protocol.denied', 'message': 'Permission denied.'}
            ]

            response = await c_mod.receive_json_from()
            assert response == [
                "question.question",
                {
                    "question": {
                        "answered": False,
                        "content": "What is your favourite colour?",
                        "id": -1,
                        "room_id": str(questions_room.id),
                        "state": "mod_queue",
                        "timestamp": -1,
                    }
                },
            ]
            await c_mod.send_json_to(
                [
                    "question.update",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                        "content": "Where is your favourite colour?",
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response == [
                "success",
                {}
            ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ask_question_unmoderated_room(unmoderated_questions_room):
    questions_room = unmoderated_questions_room
    async with world_communicator(room=unmoderated_questions_room) as c:
        await c.send_json_to(
            [
                "question.ask",
                123,
                {
                    "room": str(questions_room.id),
                    "content": "What is your favourite colour?",
                },
            ]
        )
        response = await c.receive_json_from()
        response[2]["question"]["id"] = -1
        response[2]["question"]["timestamp"] = -1
        assert response == [
            "success",
            123,
            {
                "question": {
                    "answered": False,
                    "content": "What is your favourite colour?",
                    "id": -1,
                    "room_id": str(questions_room.id),
                    "state": "visible",
                    "timestamp": -1,
                }
            },
        ]

        response = await c.receive_json_from()
        response[2]["id"] = -1
        response[2]["timestamp"] = -1
        assert response == [
            "question.question",
            {
                "question": {
                    "answered": False,
                    "content": "What is your favourite colour?",
                    "id": -1,
                    "room_id": str(questions_room.id),
                    "state": "visible",
                    "timestamp": -1,
                }
            },
        ]
