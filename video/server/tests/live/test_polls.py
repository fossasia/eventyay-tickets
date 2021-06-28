import copy
import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from tests.utils import get_token
from venueless.core.models import Poll
from venueless.routing import application


@database_sync_to_async
def get_poll(pk, room):
    return Poll.objects.get(pk=pk, room=room)


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
async def test_ask_poll_when_not_active(inactive_questions_room):
    room = inactive_questions_room
    async with world_communicator(room=room) as c:
        await c.send_json_to(
            [
                "poll.list",
                123,
                {"room": str(room.id)},
            ]
        )
        response = await c.receive_json_from()
        assert response == [
            "error",
            123,
            {
                "code": "poll.inactive",
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_poll_lifecycle(questions_room, world):
    room = questions_room
    async with world_communicator(room=room) as c:
        async with world_communicator(
            room=room, token=get_token(world, ["moderator"]), first=False
        ) as c_mod:
            await c.send_json_to(
                [
                    "poll.create",
                    123,
                    {
                        "room": str(room.id),
                        "content": "What is your favourite colour?",
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response[0] == "error"  # regular users cannot create polls

            await c_mod.send_json_to(
                [
                    "poll.create",
                    123,
                    {
                        "room": str(room.id),
                        "content": "What is your favourite colour?",
                        "options": [
                            {"content": "blue", "order": 1},
                            {"content": "red", "order": 2},
                        ],
                        "state": "draft",
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"  # regular users cannot create polls
            response = await c_mod.receive_json_from()

            poll = copy.deepcopy(response[1]["poll"])
            response[1]["poll"]["id"] = -1
            response[1]["poll"]["timestamp"] = -1
            assert response == [
                "poll.created_or_updated",
                {
                    "poll": {
                        "content": "What is your favourite colour?",
                        "id": -1,
                        "room_id": str(room.id),
                        "state": "draft",
                        "timestamp": -1,
                        "is_pinned": False,
                        "options": [
                            {
                                "content": "blue",
                                "order": 1,
                                "id": poll["options"][0]["id"],
                            },
                            {
                                "content": "red",
                                "order": 2,
                                "id": poll["options"][1]["id"],
                            },
                        ],
                        "results": {
                            poll["options"][0]["id"]: 0,
                            poll["options"][1]["id"]: 0,
                        },
                    }
                },
            ]
            await c.send_json_to(
                [
                    "poll.list",
                    123,
                    {
                        "room": str(room.id),
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]) == 0  # Draft poll is not visible

            await c_mod.send_json_to(
                [
                    "poll.list",
                    123,
                    {
                        "room": str(room.id),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]) == 1  # Draft poll is visible to mods

            await c_mod.send_json_to(
                [
                    "poll.update",
                    123,
                    {
                        "id": poll["id"],
                        "room": str(room.id),
                        "state": "open",
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            await c_mod.receive_json_from()  # Change notification
            await c.receive_json_from()  # Change notification

            # Moderator votes on the now-open poll. No notification is sent to regular user.
            await c_mod.send_json_to(
                [
                    "poll.vote",
                    123,
                    {
                        "id": poll["id"],
                        "room": str(room.id),
                        "options": [poll["options"][1]["id"]],
                    },
                ]
            )
            response = (
                await c_mod.receive_json_from()
            )  # TODO validate answered and results state
            assert response[0] == "success", response
            response = await c_mod.receive_json_from()  # Change broadcast for mods
            assert response[0] == "poll.created_or_updated", response
            assert response[1] == {
                "poll": {
                    "content": "What is your favourite colour?",
                    "id": poll["id"],
                    "room_id": str(room.id),
                    "state": "open",
                    "timestamp": poll["timestamp"],
                    "is_pinned": False,
                    "options": [
                        {"content": "blue", "order": 1, "id": poll["options"][0]["id"]},
                        {"content": "red", "order": 2, "id": poll["options"][1]["id"]},
                    ],
                    "results": {
                        poll["options"][0]["id"]: 0,
                        poll["options"][1]["id"]: 1,
                    },
                }
            }
            response = await c_mod.receive_json_from()  # Change broadcast for voters
            assert response[0] == "poll.created_or_updated", response

            await c.send_json_to(
                [
                    "poll.list",
                    123,
                    {
                        "room": str(room.id),
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]) == 1  # Open poll is now visible

            response[2][0]["timestamp"] = -1
            for option in response[2][0]["options"]:
                option["id"] = -1
            assert response == [
                "success",
                123,
                [
                    {
                        "content": "What is your favourite colour?",
                        "id": poll["id"],
                        "room_id": str(room.id),
                        "state": "open",
                        "timestamp": -1,
                        "is_pinned": False,
                        "options": [
                            {"content": "blue", "order": 1, "id": -1},
                            {"content": "red", "order": 2, "id": -1},
                        ],
                    }
                ],
            ]

            # User votes, then can see votes in list
            await c.send_json_to(
                [
                    "poll.vote",
                    123,
                    {
                        "id": poll["id"],
                        "room": str(room.id),
                        "options": [poll["options"][0]["id"]],
                    },
                ]
            )
            response = (
                await c_mod.receive_json_from()
            )  # Change broadcast for privileged users
            assert response[0] == "poll.created_or_updated", response
            response = await c_mod.receive_json_from()  # Change broadcast for voters
            assert response[0] == "poll.created_or_updated", response

            response = await c.receive_json_from()  # Success message
            assert response[0] == "success"
            response = (
                await c.receive_json_from()
            )  # Change broadcast for voters, TODO: show content with votes and answers
            assert response[0] == "poll.created_or_updated", response
            assert response[1] == {
                "poll": {
                    "content": "What is your favourite colour?",
                    "id": poll["id"],
                    "room_id": str(room.id),
                    "state": "open",
                    "timestamp": poll["timestamp"],
                    "is_pinned": False,
                    "options": [
                        {"content": "blue", "order": 1, "id": poll["options"][0]["id"]},
                        {"content": "red", "order": 2, "id": poll["options"][1]["id"]},
                    ],
                    "results": {
                        poll["options"][0]["id"]: 1,
                        poll["options"][1]["id"]: 1,
                    },
                }
            }

            # after voting, unprivileged users see results and their answers on list
            await c.send_json_to(
                [
                    "poll.list",
                    123,
                    {
                        "room": str(room.id),
                    },
                ]
            )
            response = await c.receive_json_from()
            assert response[2][0] == {
                "answers": [poll["options"][0]["id"]],
                "content": "What is your favourite colour?",
                "id": poll["id"],
                "room_id": str(room.id),
                "state": "open",
                "timestamp": poll["timestamp"],
                "is_pinned": False,
                "options": [
                    {"content": "blue", "order": 1, "id": poll["options"][0]["id"]},
                    {"content": "red", "order": 2, "id": poll["options"][1]["id"]},
                ],
                "results": {
                    poll["options"][0]["id"]: 1,
                    poll["options"][1]["id"]: 1,
                },
            }

            # Next: Moderators can pin polls
            await c_mod.send_json_to(
                [
                    "poll.pin",
                    123,
                    {
                        "id": poll["id"],
                        "room": str(room.id),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response == [
                "success",
                123,
                {
                    "id": poll["id"],
                },
            ]
            response = await c_mod.receive_json_from()
            assert response[0] == "poll.pinned"
            response = await c.receive_json_from()
            assert response[0] == "poll.pinned"

            # Next: Moderators can unpin polls
            await c_mod.send_json_to(
                [
                    "poll.unpin",
                    123,
                    {"room": str(room.id)},
                ]
            )
            response = await c_mod.receive_json_from()
            assert response == [
                "success",
                123,
                {},
            ]
            response = await c_mod.receive_json_from()
            assert response[0] == "poll.unpinned"
            response = await c.receive_json_from()
            assert response[0] == "poll.unpinned"

            poll_obj = await get_poll(room=room.id, pk=poll["id"])
            assert not poll_obj.cached_results

            # Closing the poll
            await c_mod.send_json_to(
                [
                    "poll.update",
                    123,
                    {
                        "id": poll["id"],
                        "room": str(room.id),
                        "state": "closed",
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response[0] == "success"
            await c_mod.receive_json_from()  # Change notification
            await c.receive_json_from()  # Change notification

            poll_obj = await get_poll(room=room.id, pk=poll["id"])
            assert poll_obj.cached_results

            # Finally: Moderators can delete polls
            await c_mod.send_json_to(
                [
                    "poll.delete",
                    123,
                    {
                        "id": poll["id"],
                        "room": str(room.id),
                    },
                ]
            )
            response = await c_mod.receive_json_from()
            assert response == [
                "success",
                123,
                {
                    "poll": poll["id"],
                },
            ]
            await c_mod.receive_json_from()  # Delete broadcast

            response = await c.receive_json_from()  # Delete broadcast
            assert response == [
                "poll.deleted",
                {
                    "id": poll["id"],
                    "room": str(room.id),
                },
            ]
