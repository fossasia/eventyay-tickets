import datetime
import uuid
from contextlib import asynccontextmanager

import jwt
import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from tests.utils import get_token
from venueless.core.models import User
from venueless.core.services.user import get_user_by_token_id
from venueless.routing import application


@asynccontextmanager
async def world_communicator():
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_client_id(world):
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_anonymous_access(world):
    world.trait_grants["attendee"] = ["ticket-holder"]
    await database_sync_to_async(world.save)()
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[1] == {"code": "auth.denied"}
        assert (await database_sync_to_async(User.objects.count)()) == 0


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_banned(world):
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        user_id = response[1]["user.config"]["id"]
    user = await database_sync_to_async(User.objects.get)(pk=user_id)
    user.moderation_state = User.ModerationState.BANNED
    await database_sync_to_async(user.save)()
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[1] == {"code": "auth.denied"}


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_action_before_auth():
    async with world_communicator() as c:
        await c.send_json_to(["chat.join", 124, {"client_id": 4}])
        response = await c.receive_json_from()
        assert response == ["error", 124, {"code": "protocol.unauthenticated"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_without_client_id():
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {}])
        response = await c.receive_json_from()
        assert response == ["error", {"code": "auth.missing_id_or_token"}]


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("index", [0, 1])
async def test_auth_with_jwt_token(index, world):
    config = world.config["JWT_secrets"][index]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1]["world.config"]["permissions"]) == {
            "world:view",
        }
        assert set(response[1]["world.config"]["rooms"][0]["permissions"]) == {
            "room:view",
            "room:chat.read",
            "room:chat.join",
            "room:chat.send",
            "room:bbb.join",
            "room:question.vote",
            "room:question.read",
            "room:question.ask",
            "room:roulette.join",
        }
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_invalid_jwt_token(world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"] + "aaaa", algorithm="HS256")
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "error"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_update_user():
    async with world_communicator() as c, world_communicator() as c2, world_communicator() as c3:
        await c.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        await c2.send_json_to(["authenticate", {"client_id": "4"}])
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        user_id = response[1]["user.config"]["id"]

        response = await c2.receive_json_from()
        assert response[0] == "authenticated"

        await c.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Cool User"}}]
        )
        response = await c.receive_json_from()
        assert response == ["success", 123, {}], response

        response = await c2.receive_json_from()
        assert response == [
            "user.updated",
            {
                "profile": {"display_name": "Cool User"},
                "badges": [],
                "inactive": False,
                "id": user_id,
            },
        ]

        await c3.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c3.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        assert response[1]["user.config"]["profile"]["display_name"] == "Cool User"
        assert response[1]["user.config"]["id"] == user_id


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_user_command():
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        await c.send_json_to(["user.foobar", 123, {"display_name": "Cool User"}])
        response = await c.receive_json_from()
        assert response == ["error", 123, {"code": "user.unsupported_command"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_jwt_token_update_traits(world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    payload["traits"] = ["chat.read"]
    token2 = jwt.encode(payload, config["secret"], algorithm="HS256")
    async with world_communicator() as c, world_communicator() as c2:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        assert (
            await database_sync_to_async(get_user_by_token_id)("sample", "123456")
        ).traits == [
            "chat.read",
            "foo.bar",
        ]

        await c2.send_json_to(["authenticate", {"token": token2}])
        response = await c2.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        assert (
            await database_sync_to_async(get_user_by_token_id)("sample", "123456")
        ).traits == ["chat.read"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_jwt_token_twice(world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    async with world_communicator() as c, world_communicator() as c2:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        assert (
            await database_sync_to_async(get_user_by_token_id)("sample", "123456")
        ).traits == [
            "chat.read",
            "foo.bar",
        ]

        await c2.send_json_to(["authenticate", {"token": token}])
        response = await c2.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        assert (
            await database_sync_to_async(get_user_by_token_id)("sample", "123456")
        ).traits == [
            "chat.read",
            "foo.bar",
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_fetch_user():
    async with world_communicator() as c, world_communicator() as c2:
        await c.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        user_id = response[1]["user.config"]["id"]

        await c.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Cool User"}}]
        )
        response = await c.receive_json_from()
        assert response == ["success", 123, {}], response

        await c2.send_json_to(["authenticate", {"client_id": "5"}])
        await c2.receive_json_from()

        await c2.send_json_to(["user.fetch", 14, {"id": user_id}])
        response = await c2.receive_json_from()
        assert response == [
            "success",
            14,
            {
                "id": user_id,
                "profile": {"display_name": "Cool User"},
                "badges": [],
                "inactive": False,
            },
        ]

        await c2.send_json_to(["user.fetch", 14, {"ids": [user_id, str(uuid.uuid4())]}])
        response = await c2.receive_json_from()
        assert response == [
            "success",
            14,
            {
                user_id: {
                    "id": user_id,
                    "badges": [],
                    "inactive": False,
                    "profile": {"display_name": "Cool User"},
                }
            },
        ]

        await c2.send_json_to(["user.fetch", 14, {"id": str(uuid.uuid4())}])
        response = await c2.receive_json_from()
        assert response == ["error", 14, {"code": "user.not_found"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_jwt_token_and_permission_traits(world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["moderator", "speaker"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {
            "world.config",
            "user.config",
            "chat.channels",
            "chat.read_pointers",
            "exhibition",
        }
        assert set(response[1]["world.config"]["permissions"]) == {
            "world:view",
            "room:view",
            "room:chat.read",
            "room:chat.join",
            "room:chat.send",
            "room:roulette.join",
            "room:bbb.join",
            "room:bbb.moderate",
            "room:chat.moderate",
            "room:bbb.recordings",
            "room:announce",
            "world:announce",
            "world:chat.direct",
            "world:exhibition.contact",
            "room:question.vote",
            "room:question.read",
            "room:question.moderate",
            "room:question.ask",
        }
        assert set(response[1]["world.config"]["rooms"][0]["permissions"]) == {
            "room:view",
            "room:chat.read",
            "room:chat.join",
            "room:chat.send",
            "room:roulette.join",
            "room:bbb.join",
            "room:bbb.moderate",
            "room:bbb.recordings",
            "room:chat.moderate",
            "room:announce",
            "room:question.vote",
            "room:question.read",
            "room:question.moderate",
            "room:question.ask",
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_private_rooms_in_world_config(
    world, bbb_room, chat_room, stream_room
):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["blablabla"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")

    bbb_room.trait_grants = {}
    await database_sync_to_async(bbb_room.save)()
    chat_room.trait_grants = {}
    await database_sync_to_async(chat_room.save)()

    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(r["name"] for r in response[1]["world.config"]["rooms"]) == {
            "About",
            "More Info",
            "Exhibition Hall",
            "Plenum",
            "Stage 2",
            "Not Streaming",
        }

    chat_room.trait_grants = {
        "participant": [["unknowen", "blablabla"]],
    }
    await database_sync_to_async(chat_room.save)()
    stream_room.trait_grants = {
        "participant": ["blablabla"],
    }
    await database_sync_to_async(stream_room.save)()

    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(r["name"] for r in response[1]["world.config"]["rooms"]) == {
            "About",
            "More Info",
            "Exhibition Hall",
            "Plenum",
            "Stage 2",
            "Not Streaming",
            "Chat",
        }

    await database_sync_to_async(bbb_room.role_grants.create)(
        user=await database_sync_to_async(User.objects.get)(),
        role="participant",
        world=world,
    )

    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(r["name"] for r in response[1]["world.config"]["rooms"]) == {
            "About",
            "More Info",
            "Exhibition Hall",
            "Plenum",
            "Stage 2",
            "Not Streaming",
            "Chat",
            "Gruppenraum 1",
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_list_users(world):
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        user_id = response[1]["user.config"]["id"]

        await c.send_json_to(["user.list", 14, {}])
        response = await c.receive_json_from()
        assert response[0] == "error"

        world.trait_grants["admin"] = []
        await database_sync_to_async(world.save)()

        await c.send_json_to(["user.list", 14, {}])
        response = await c.receive_json_from()
        assert response == [
            "success",
            14,
            {
                "results": [
                    {
                        "id": user_id,
                        "profile": {},
                        "moderation_state": "",
                        "inactive": False,
                        "badges": [],
                        "token_id": None,
                    }
                ]
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ban_user(world):
    async with world_communicator() as c_admin:
        token = get_token(world, ["admin"])
        await c_admin.send_json_to(["authenticate", {"token": token}])
        await c_admin.receive_json_from()

        async with world_communicator() as c_user:
            await c_user.send_json_to(["authenticate", {"client_id": "4"}])
            response = await c_user.receive_json_from()
            user_id = response[1]["user.config"]["id"]

            await c_admin.send_json_to(["user.ban", 14, {"id": user_id}])
            response = await c_admin.receive_json_from()
            assert response[0] == "success"

            await c_admin.send_json_to(["user.ban", 14, {"id": str(uuid.uuid4())}])
            response = await c_admin.receive_json_from()
            assert response[0] == "error"

            assert ["connection.reload", {}] == await c_user.receive_json_from()
            assert {"type": "websocket.close"} == await c_user.receive_output(timeout=3)

        async with world_communicator() as c_user:
            await c_user.send_json_to(["authenticate", {"client_id": "4"}])
            response = await c_user.receive_json_from()
            assert response[1] == {"code": "auth.denied"}

        await c_admin.send_json_to(["user.reactivate", 14, {"id": user_id}])
        response = await c_admin.receive_json_from()
        assert response[0] == "success"

        await c_admin.send_json_to(["user.reactivate", 14, {"id": str(uuid.uuid4())}])
        response = await c_admin.receive_json_from()
        assert response[0] == "error"

        async with world_communicator() as c_user:
            await c_user.send_json_to(["authenticate", {"client_id": "4"}])
            response = await c_user.receive_json_from()
            assert response[0] == "authenticated"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_silence_user(world, volatile_chat_room):
    async with world_communicator() as c_user, world_communicator() as c_admin:
        token = get_token(world, ["admin"])
        await c_admin.send_json_to(["authenticate", {"token": token}])
        await c_admin.receive_json_from()

        await c_user.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c_user.receive_json_from()
        user_id = response[1]["user.config"]["id"]

        await c_user.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await c_user.receive_json_from()

        await c_user.send_json_to(
            ["chat.join", 123, {"channel": str(volatile_chat_room.channel.id)}]
        )
        await c_user.receive_json_from()
        await c_user.receive_json_from()
        await c_user.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(volatile_chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c_user.receive_json_from()
        assert response[0] == "success", response
        await c_user.receive_json_from()

        await c_admin.send_json_to(["user.silence", 14, {"id": user_id}])
        response = await c_admin.receive_json_from()
        assert response[0] == "success"

        await c_admin.send_json_to(["user.silence", 14, {"id": str(uuid.uuid4())}])
        response = await c_admin.receive_json_from()
        assert response[0] == "error"

        assert ["connection.reload", {}] == await c_user.receive_json_from()
        assert {"type": "websocket.close"} == await c_user.receive_output(timeout=3)

    async with world_communicator() as c_user:
        await c_user.send_json_to(["authenticate", {"client_id": "4"}])
        await c_user.receive_json_from()

        await c_user.send_json_to(
            ["chat.join", 123, {"channel": str(volatile_chat_room.channel.id)}]
        )
        await c_user.receive_json_from()
        await c_user.receive_json_from()
        await c_user.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": str(volatile_chat_room.channel.id),
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                },
            ]
        )
        response = await c_user.receive_json_from()
        assert response == [
            "error",
            123,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_block_user(world):
    async with world_communicator() as c_blocker:
        token = get_token(world, [])
        await c_blocker.send_json_to(["authenticate", {"token": token}])
        await c_blocker.receive_json_from()

        async with world_communicator() as c_blockee:
            await c_blockee.send_json_to(["authenticate", {"client_id": "4"}])
            response = await c_blockee.receive_json_from()
            user_id = response[1]["user.config"]["id"]

            await c_blocker.send_json_to(["user.block", 14, {"id": user_id}])
            response = await c_blocker.receive_json_from()
            assert response[0] == "success"

            await c_blocker.send_json_to(["user.list.blocked", 14, {}])
            response = await c_blocker.receive_json_from()
            assert response[0] == "success"
            assert response[2]["users"][0]["id"] == user_id

            await c_blocker.send_json_to(["user.block", 14, {"id": str(uuid.uuid4())}])
            response = await c_blocker.receive_json_from()
            assert response[0] == "error"

        await c_blocker.send_json_to(["user.unblock", 14, {"id": user_id}])
        response = await c_blocker.receive_json_from()
        assert response[0] == "success"

        await c_blocker.send_json_to(["user.list.blocked", 14, {}])
        response = await c_blocker.receive_json_from()
        assert response[0] == "success"
        assert not response[2]["users"]

        await c_blocker.send_json_to(["user.unblock", 14, {"id": str(uuid.uuid4())}])
        response = await c_blocker.receive_json_from()
        assert response[0] == "error"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_list_search_users(world):
    async with world_communicator() as c, world_communicator() as c_user1, world_communicator() as c_user2:
        # User 1
        await c.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        user_id = response[1]["user.config"]["id"]
        await c.send_json_to(
            ["user.update", 14, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await c.receive_json_from()

        # User 2
        await c_user1.send_json_to(["authenticate", {"client_id": "5"}])
        response = await c_user1.receive_json_from()
        assert response[0] == "authenticated"
        user1_id = response[1]["user.config"]["id"]
        await c_user1.send_json_to(
            ["user.update", 14, {"profile": {"display_name": "Foo Esidisi"}}]
        )
        await c_user1.receive_json_from()

        # User 3
        await c_user2.send_json_to(["authenticate", {"client_id": "6"}])
        response = await c_user2.receive_json_from()
        assert response[0] == "authenticated"
        user2_id = response[1]["user.config"]["id"]
        await c_user2.send_json_to(
            ["user.update", 14, {"profile": {"display_name": "Foo Kars"}}]
        )
        await c_user2.receive_json_from()

        # Search
        await c.send_json_to(
            [
                "user.list.search",
                14,
                {
                    "page": 0,
                    "search_term": "",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2] == {
            "results": [],
            "isLastPage": True,
        }

        await c.send_json_to(
            [
                "user.list.search",
                14,
                {
                    "page": 1,
                    "search_term": "",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2] == {
            "results": [],
            "isLastPage": True,
        }

        await c.send_json_to(
            [
                "user.list.search",
                14,
                {
                    "page": 1,
                    "search_term": "Fighter",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2] == {
            "results": [
                {
                    "id": user_id,
                    "badges": [],
                    "inactive": False,
                    "profile": {"display_name": "Foo Fighter"},
                }
            ],
            "isLastPage": True,
        }

        world.config["user_list"]["page_size"] = 2
        await database_sync_to_async(world.save)()

        await c.send_json_to(
            [
                "user.list.search",
                14,
                {
                    "page": 1,
                    "search_term": "Foo",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["results"][0]["id"] in [user_id, user1_id, user2_id]
        assert response[2]["results"][1]["id"] in [user_id, user1_id, user2_id]

        await c.send_json_to(
            [
                "user.list.search",
                14,
                {
                    "page": 2,
                    "search_term": "Foo",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["results"][0]["id"] in [user_id, user1_id, user2_id]

        await c.send_json_to(
            [
                "user.list.search",
                14,
                {
                    "page": 3,
                    "search_term": "Foo",
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2] == {
            "results": [],
            "isLastPage": True,
        }


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_badges(world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": "123456",
        "traits": ["moderator", "speaker"],
    }
    world.config["trait_badges_map"] = {"moderator": "Crew"}
    await database_sync_to_async(world.save)()
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        id = response[1]["user.config"]["id"]

        await c.send_json_to(["user.fetch", 14, {"id": id}])
        response = await c.receive_json_from()
        assert response[2]["badges"] == ["Crew"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_online_status(world):
    async with world_communicator() as c_admin:
        token = get_token(world, ["admin"])
        await c_admin.send_json_to(["authenticate", {"token": token}])
        await c_admin.receive_json_from()
        async with world_communicator() as c_user:
            await c_user.send_json_to(["authenticate", {"client_id": "4"}])
            response = await c_user.receive_json_from()
            user_id = response[1]["user.config"]["id"]

            await c_admin.send_json_to(["user.online_status", 123, {"ids": [user_id]}])
            assert (await c_admin.receive_json_from())[2] == {user_id: True}
        await c_admin.send_json_to(["user.online_status", 123, {"ids": [user_id]}])
        assert (await c_admin.receive_json_from())[2] == {user_id: False}
