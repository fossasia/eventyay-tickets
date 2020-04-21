import datetime
from contextlib import asynccontextmanager

import jwt
import pytest
from channels.testing import WebsocketCommunicator

from stayseated.core.services.user import get_user_by_token_id
from stayseated.core.services.world import get_world_config
from stayseated.routing import application


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
async def test_auth_with_client_id():
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}


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
async def test_auth_with_jwt_token(index):
    world_config = await get_world_config("sample")
    config = world_config["world"]["JWT_secrets"][index]
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
    token = jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_invalid_jwt_token():
    world_config = await get_world_config("sample")
    config = world_config["world"]["JWT_secrets"][0]
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
    token = jwt.encode(payload, config["secret"] + "aaaa", algorithm="HS256").decode(
        "utf-8"
    )
    async with world_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "error"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_update_user():
    async with world_communicator() as c, world_communicator() as c2:
        await c.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}
        user_id = response[1]["user.config"]["id"]

        await c.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Cool User"}}]
        )
        response = await c.receive_json_from()
        assert response == ["success", 123, {}], response

        await c2.send_json_to(["authenticate", {"client_id": "4"}])
        response = await c2.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}
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
        assert response == ["error", 123, {"code": "user.unknown_command"}]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_jwt_token_update_traits():
    world_config = await get_world_config("sample")
    config = world_config["world"]["JWT_secrets"][0]
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
    token = jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")
    payload["traits"] = ["chat.read"]
    token2 = jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")
    async with world_communicator() as c, world_communicator() as c2:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}
        assert (await get_user_by_token_id("sample", "123456")).traits == [
            "chat.read",
            "foo.bar",
        ]

        await c2.send_json_to(["authenticate", {"token": token2}])
        response = await c2.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}
        assert (await get_user_by_token_id("sample", "123456")).traits == ["chat.read"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_jwt_token_twice():
    world_config = await get_world_config("sample")
    config = world_config["world"]["JWT_secrets"][0]
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
    token = jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")
    async with world_communicator() as c, world_communicator() as c2:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}
        assert (await get_user_by_token_id("sample", "123456")).traits == [
            "chat.read",
            "foo.bar",
        ]

        await c2.send_json_to(["authenticate", {"token": token}])
        response = await c2.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"world.config", "user.config"}
        assert (await get_user_by_token_id("sample", "123456")).traits == [
            "chat.read",
            "foo.bar",
        ]
