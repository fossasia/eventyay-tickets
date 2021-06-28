import uuid
from contextlib import asynccontextmanager

import pytest
from channels.testing import WebsocketCommunicator

from tests.utils import get_token
from venueless.routing import application


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
        async with world_communicator(
            room=questions_room, token=get_token(world, ["moderator"]), first=False
        ) as c_mod:
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
                        "score": 0,
                        "timestamp": -1,
                        "is_pinned": False,
                    }
                },
            ]
            await c.send_json_to(
                [
                    "question.list",
                    123,
                    {
                        "room": str(questions_room.id),
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]) == 1
            assert response[2][0]["id"] == question_id
            assert response[2][0]["voted"] is False
            await c.send_json_to(
                [
                    "question.update",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                        "content": "When is your favourite colour?",
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response == [
                "error",
                123,
                {"code": "protocol.denied", "message": "Permission denied."},
            ]

            response = await c_mod.receive_json_from()
            response[1]["question"]["id"] = -1
            response[1]["question"]["timestamp"] = -1
            assert response == [
                "question.created_or_updated",
                {
                    "question": {
                        "answered": False,
                        "is_pinned": False,
                        "content": "What is your favourite colour?",
                        "id": -1,
                        "room_id": str(questions_room.id),
                        "state": "mod_queue",
                        "score": 0,
                        "timestamp": -1,
                    }
                },
            ]
            await c_mod.send_json_to(
                [
                    "question.list",
                    123,
                    {
                        "room": str(questions_room.id),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]) == 1
            assert response[2][0]["id"] == question_id
            assert response[2][0]["voted"] is False
            await c_mod.send_json_to(
                [
                    "question.update",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                        "content": "When is your favourite colour?",
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            response[2]["question"]["id"] = -1
            response[2]["question"]["timestamp"] = -1
            assert response == [
                "success",
                123,
                {
                    "question": {
                        "answered": False,
                        "is_pinned": False,
                        "content": "When is your favourite colour?",
                        "id": -1,
                        "room_id": str(questions_room.id),
                        "state": "mod_queue",
                        "score": 0,
                        "timestamp": -1,
                    }
                },
            ]
            await c_mod.receive_json_from()  # Update broadcast
            # Regular users do not get an update.
            # We test this implicitly by running the full test instead of the following code,
            # because getting a timeout once ruins the consumer, apparently. The following holds true, though:
            # import asyncio
            # with pytest.raises(asyncio.TimeoutError):
            #     await c.receive_json_from()

            # Mods can make questions public

            await c_mod.send_json_to(
                [
                    "question.update",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                        "state": "visible",
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            response[2]["question"]["id"] = -1
            response[2]["question"]["timestamp"] = -1
            assert response == [
                "success",
                123,
                {
                    "question": {
                        "answered": False,
                        "is_pinned": False,
                        "content": "When is your favourite colour?",
                        "id": -1,
                        "room_id": str(questions_room.id),
                        "state": "visible",
                        "score": 0,
                        "timestamp": -1,
                    }
                },
            ]
            await c_mod.receive_json_from()  # Update broadcast
            response = await c.receive_json_from()  # All users get update broadcast
            response[1]["question"]["timestamp"] = -1
            assert response == [
                "question.created_or_updated",
                {
                    "question": {
                        "answered": False,
                        "is_pinned": False,
                        "content": "When is your favourite colour?",
                        "id": question_id,
                        "room_id": str(questions_room.id),
                        "state": "visible",
                        "score": 0,
                        "timestamp": -1,
                    }
                },
            ]
            # Next: Moderators can pin questions
            await c_mod.send_json_to(
                [
                    "question.pin",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response == [
                "success",
                123,
                {
                    "id": question_id,
                },
            ]
            await c_mod.receive_json_from()  # Pin broadcast

            response = await c.receive_json_from()  # Pin broadcast
            assert response == [
                "question.pinned",
                {
                    "id": question_id,
                    "room": str(questions_room.id),
                },
            ]

            # Next: Moderators can unpin questions
            await c_mod.send_json_to(
                [
                    "question.unpin",
                    123,
                    {"room": str(questions_room.id)},
                ]
            )
            response = await c_mod.receive_json_from()
            assert response == [
                "success",
                123,
                {},
            ]
            await c_mod.receive_json_from()  # Unpin broadcast

            response = await c.receive_json_from()  # Unpin broadcast
            assert response == [
                "question.unpinned",
                {"room": str(questions_room.id)},
            ]

            # Finally: Moderators can delete questions
            await c_mod.send_json_to(
                [
                    "question.delete",
                    123,
                    {
                        "id": question_id,
                        "room": str(questions_room.id),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response == [
                "success",
                123,
                {
                    "question": question_id,
                },
            ]
            await c_mod.receive_json_from()  # Delete broadcast

            response = await c.receive_json_from()  # Delete broadcast
            assert response == [
                "question.deleted",
                {
                    "id": question_id,
                    "room": str(questions_room.id),
                },
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
        question_id = response[2]["question"]["id"]
        response[2]["question"]["id"] = -1
        response[2]["question"]["timestamp"] = -1
        assert response == [
            "success",
            123,
            {
                "question": {
                    "answered": False,
                    "is_pinned": False,
                    "content": "What is your favourite colour?",
                    "id": -1,
                    "room_id": str(questions_room.id),
                    "state": "visible",
                    "score": 0,
                    "timestamp": -1,
                }
            },
        ]

        response = await c.receive_json_from()
        response[1]["question"]["id"] = -1
        response[1]["question"]["timestamp"] = -1
        assert response == [
            "question.created_or_updated",
            {
                "question": {
                    "answered": False,
                    "is_pinned": False,
                    "content": "What is your favourite colour?",
                    "id": -1,
                    "room_id": str(questions_room.id),
                    "state": "visible",
                    "score": 0,
                    "timestamp": -1,
                }
            },
        ]

        # Vote for the question
        await c.send_json_to(
            [
                "question.vote",
                123,
                {
                    "room": str(questions_room.id),
                    "id": question_id,
                    "vote": True,
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success", response
        assert response[2]["question"]["score"] == 1, response

        response = await c.receive_json_from()
        response[1]["question"]["id"] = -1
        response[1]["question"]["timestamp"] = -1
        assert response == [
            "question.created_or_updated",
            {
                "question": {
                    "answered": False,
                    "is_pinned": False,
                    "content": "What is your favourite colour?",
                    "id": -1,
                    "room_id": str(questions_room.id),
                    "state": "visible",
                    "score": 1,
                    "timestamp": -1,
                }
            },
        ]
        # Question is listed as voted
        await c.send_json_to(
            [
                "question.list",
                123,
                {
                    "room": str(questions_room.id),
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert len(response[2]) == 1
        assert response[2][0]["id"] == question_id
        assert response[2][0]["voted"] is True

        # Unvote the question

        await c.send_json_to(
            [
                "question.vote",
                123,
                {
                    "room": str(questions_room.id),
                    "id": question_id,
                    "vote": False,
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success", response
        assert response[2]["question"]["score"] == 0, response

        response = await c.receive_json_from()
        response[1]["question"]["id"] = -1
        response[1]["question"]["timestamp"] = -1
        assert response == [
            "question.created_or_updated",
            {
                "question": {
                    "answered": False,
                    "is_pinned": False,
                    "content": "What is your favourite colour?",
                    "id": -1,
                    "room_id": str(questions_room.id),
                    "state": "visible",
                    "score": 0,
                    "timestamp": -1,
                }
            },
        ]
