import uuid
from contextlib import asynccontextmanager

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from tests.utils import get_token_header
from venueless.routing import application


@pytest.mark.django_db
def test_room_list(client, world):
    r = client.get(
        "/api/v1/worlds/sample/rooms/",
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 200
    assert r.data["count"] == 8
    assert r.data["results"][0] == {
        "id": str(world.rooms.first().id),
        "deleted": False,
        "name": "About",
        "trait_grants": {"viewer": [], "participant": []},
        "module_config": [
            {
                "type": "page.landing",
                "config": {
                    "header_background_color": "#673ab7",
                    "header_image": "/eventyay-video-logo.svg",
                    "content": "# Welcome to this example event!\n\nYou might notice that the dates for the current "
                    "sessions are not actually your current time and that time does not progress. That's "
                    "because we froze time – only in this demo of course – with the power of programming!"
                    "\n\nHave a look around!",
                },
            }
        ],
        "description": "UNUSED",
        "pretalx_id": 0,
        "sorting_priority": 0,
        "schedule_data": None,
    }


@pytest.mark.django_db
def test_room_detail(client, world):
    r = client.get(
        f"/api/v1/worlds/sample/rooms/{str(world.rooms.first().id)}/",
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 200
    assert r.data == {
        "id": str(world.rooms.first().id),
        "deleted": False,
        "trait_grants": {"viewer": [], "participant": []},
        "name": "About",
        "module_config": [
            {
                "type": "page.landing",
                "config": {
                    "header_background_color": "#673ab7",
                    "header_image": "/eventyay-video-logo.svg",
                    "content": "# Welcome to this example event!\n\nYou might notice that the dates for the current "
                    "sessions are not actually your current time and that time does not progress. That's "
                    "because we froze time – only in this demo of course – with the power of programming!"
                    "\n\nHave a look around!",
                },
            }
        ],
        "description": "UNUSED",
        "pretalx_id": 0,
        "sorting_priority": 0,
        "schedule_data": None,
    }


@pytest.mark.django_db
def test_room_delete(client, world):
    world.trait_grants["apiuser"] = ["foobartrait", "admin"]
    world.save()
    rid = world.rooms.first().id

    r = client.delete(
        f"/api/v1/worlds/sample/rooms/{str(rid)}/",
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 403
    r = client.delete(
        f"/api/v1/worlds/sample/rooms/{str(rid)}/",
        HTTP_AUTHORIZATION=get_token_header(world, ["admin", "api", "foobartrait"]),
    )
    assert r.status_code == 204
    assert not world.rooms.filter(id=rid).exists()


@pytest.mark.django_db
def test_room_update(client, world):
    world.trait_grants["apiuser"] = ["foobartrait", "admin"]
    world.save()
    rid = world.rooms.first().id

    r = client.patch(
        f"/api/v1/worlds/sample/rooms/{str(rid)}/",
        dataß={"name": "Forum"},
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 403
    r = client.patch(
        f"/api/v1/worlds/sample/rooms/{str(rid)}/",
        data={
            "name": "Forum",
        },
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world, ["admin", "api", "foobartrait"]),
    )
    assert r.status_code == 200
    assert world.rooms.get(id=rid).name == "Forum"


@pytest.mark.django_db
def test_room_create(client, world):
    world.trait_grants["apiuser"] = ["foobartrait", "admin"]
    world.save()

    r = client.post(
        "/api/v1/worlds/sample/rooms/",
        data={
            "name": "Forum",
            "sorting_priority": 100,
        },
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 403
    r = client.post(
        "/api/v1/worlds/sample/rooms/",
        data={
            "name": "Forum",
            "sorting_priority": 100,
            "module_config": [{"type": "unknown"}],
        },
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world, ["admin", "api", "foobartrait"]),
    )
    assert r.status_code == 201
    assert world.rooms.last().name == "Forum"
    assert str(world.rooms.last().id) == r.data["id"]

    r = client.post(
        "/api/v1/worlds/sample/rooms/",
        format="json",
        data={
            "name": "Forum",
            "sorting_priority": 102,
            "module_config": [{"type": "chat.native"}],
        },
        HTTP_AUTHORIZATION=get_token_header(world, ["admin", "api", "foobartrait"]),
    )
    assert r.status_code == 201
    assert world.rooms.last().name == "Forum"
    assert str(world.rooms.last().id) == r.data["id"]
    assert world.rooms.last().channel


@asynccontextmanager
async def world_communicator(client_id=None, named=True):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
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
async def test_push_world_update(client, world):
    async with world_communicator() as c:
        r = await sync_to_async(client.get)(
            "/api/v1/worlds/sample/rooms/",
            HTTP_AUTHORIZATION=get_token_header(world),
        )
        assert r.status_code == 200
        rid = r.data["results"][0]["id"]
        r = await sync_to_async(client.patch)(
            f"/api/v1/worlds/sample/rooms/{str(rid)}/",
            format="json",
            data={"name": "Forum"},
            HTTP_AUTHORIZATION=get_token_header(world),
        )
        assert r.status_code == 200
        w = await c.receive_json_from()
        assert w[0] == "world.updated"
