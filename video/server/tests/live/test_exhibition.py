import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from venueless.core.models import User
from venueless.routing import application


@asynccontextmanager
async def world_communicator(token=None):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    if token:
        await communicator.send_json_to(["authenticate", {"token": token}])
    else:
        await communicator.send_json_to(
            ["authenticate", {"client_id": str(uuid.uuid4())}]
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
async def test_list_short(world, exhibition_room):
    async with world_communicator() as c:
        await c.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        for e in response[2]["exhibitors"]:
            del e["id"]
            assert e in [
                {
                    "name": "Tube GmbH",
                    "tagline": "Ihr Partner im Großhandel",
                    "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod "
                    "tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero "
                    "eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea tak",
                    "logo": "https://via.placeholder.com/150",
                    "size": "1x1",
                    "sorting_priority": 1,
                },
                {
                    "name": "Messebau Schmidt UG",
                    "tagline": "Handwerk aus Leidenschaft",
                    "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod"
                    " tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero "
                    "eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea tak",
                    "logo": "https://via.placeholder.com/150",
                    "size": "1x1",
                    "sorting_priority": 0,
                },
            ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get(world, exhibition_room):
    async with world_communicator() as c:
        await c.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c.receive_json_from()
        e_id = response[2]["exhibitors"].pop()["id"]

        await c.send_json_to(["exhibition.get", 123, {"exhibitor": str(e_id)}])
        response = await c.receive_json_from()
        assert response[0] == "success"

        e = response[2]["exhibitor"]
        del e["id"]
        assert e in [
            {
                "name": "Messebau Schmidt UG",
                "tagline": "Handwerk aus Leidenschaft",
                "logo": "https://via.placeholder.com/150",
                "text": "# Wir liefern wovon andere nur reden\n\nHallo!\nDas ist ein Markdowntext!",
                "size": "1x1",
                "sorting_priority": 0,
                "links": [
                    {"display_text": "Website", "url": "http://example.org/"},
                    {
                        "display_text": "Info Broschüre",
                        "url": "https://de.wikipedia.org/wiki/Messebau",
                    },
                ],
                "social_media_links": [
                    {"display_text": "XING", "url": "https://www.xing.com/"}
                ],
                "staff": [],
            },
            {
                "name": "Tube GmbH",
                "tagline": "Ihr Partner im Großhandel",
                "logo": "https://via.placeholder.com/150",
                "text": "# Gastro und mehr\n\nVon Apfel bis Zebra, wir liefern!",
                "size": "1x1",
                "sorting_priority": 1,
                "links": [],
                "social_media_links": [
                    {"display_text": "linkedin", "url": "https://www.linkedin.com/"}
                ],
                "staff": [],
            },
        ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_invalid_id(world, exhibition_room):
    async with world_communicator() as c:
        await c.send_json_to(["exhibition.get", 123, {"exhibitor": str(uuid.uuid4())}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "exhibition.unknown_exhibitor"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_contact_cancel(world, exhibition_room):
    async with world_communicator() as c_staff, world_communicator() as c1:
        await database_sync_to_async(exhibition_room.role_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c1.context["user.config"]["id"]
            ),
            world=world,
            role="participant",
        )

        # get an exhibitor
        await c_staff.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        e = response[2]["exhibitors"][0]

        # add staff
        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c_staff.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )
        await c_staff.send_json_to(
            [
                "exhibition.add_staff",
                123,
                {
                    "exhibitor": str(e["id"]),
                    "user": str(c_staff.context["user.config"]["id"]),
                },
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"

        await c_staff.send_json_to(["exhibition.get", 123, {"exhibitor": str(e["id"])}])
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        assert response[2]["exhibitor"]["staff"][0] == str(
            c_staff.context["user.config"]["id"]
        )

        # issue contact request
        await c1.send_json_to(
            [
                "exhibition.contact",
                123,
                {"exhibitor": str(e["id"]), "room": str(exhibition_room.pk)},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"
        request_id = response[2]["contact_request"]["id"]

        response = await c_staff.receive_json_from()
        assert response[0] == "contact_request"
        assert response[1]["id"] == request_id

        await c1.send_json_to(
            [
                "exhibition.contact_cancel",
                123,
                {"contact_request": request_id, "room": str(exhibition_room.pk)},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c_staff.receive_json_from()
        assert response[0] == "contact_request_close"
        assert response[1]["id"] == request_id


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_contact(world, exhibition_room):
    async with world_communicator() as c_staff, world_communicator() as c1:
        await database_sync_to_async(exhibition_room.role_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c1.context["user.config"]["id"]
            ),
            world=world,
            role="participant",
        )

        # get an exhibitor
        await c_staff.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        e = response[2]["exhibitors"][0]

        # add staff
        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c_staff.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )
        await c_staff.send_json_to(
            [
                "exhibition.add_staff",
                123,
                {
                    "exhibitor": str(e["id"]),
                    "user": str(c_staff.context["user.config"]["id"]),
                },
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"

        await c_staff.send_json_to(["exhibition.get", 123, {"exhibitor": str(e["id"])}])
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        assert response[2]["exhibitor"]["staff"][0] == str(
            c_staff.context["user.config"]["id"]
        )

        # issue contact request
        await c1.send_json_to(
            [
                "exhibition.contact",
                123,
                {"exhibitor": str(e["id"]), "room": str(exhibition_room.pk)},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        # receive request and answer
        response = await c_staff.receive_json_from()
        assert response[0] == "contact_request"
        contact_request_id = response[1]["id"]
        await c_staff.send_json_to(
            [
                "exhibition.contact_accept",
                123,
                {"contact_request": str(contact_request_id)},
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        response = await c1.receive_json_from()
        assert response[0] == "contact_accepted"
        response = await c_staff.receive_json_from()
        assert response[0] == "contact_request_close"

        # try to answer same request twice
        await c_staff.send_json_to(
            [
                "exhibition.contact_accept",
                123,
                {"contact_request": str(contact_request_id)},
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "exhibition.unknown_contact_request"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_contact_not_staff(world, exhibition_room):
    async with world_communicator() as c_staff, world_communicator() as c1, world_communicator() as c2:
        await database_sync_to_async(exhibition_room.role_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c1.context["user.config"]["id"]
            ),
            world=world,
            role="participant",
        )
        await database_sync_to_async(exhibition_room.role_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c2.context["user.config"]["id"]
            ),
            world=world,
            role="participant",
        )

        # get an exhibitor
        await c_staff.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        e = response[2]["exhibitors"][0]

        # add staff
        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c_staff.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )
        await c_staff.send_json_to(
            [
                "exhibition.add_staff",
                123,
                {
                    "exhibitor": str(e["id"]),
                    "user": str(c_staff.context["user.config"]["id"]),
                },
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"

        await c_staff.send_json_to(["exhibition.get", 123, {"exhibitor": str(e["id"])}])
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        assert response[2]["exhibitor"]["staff"][0] == str(
            c_staff.context["user.config"]["id"]
        )

        # issue contact request
        await c1.send_json_to(
            [
                "exhibition.contact",
                123,
                {"exhibitor": str(e["id"]), "room": str(exhibition_room.pk)},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        # receive request and answer
        response = await c_staff.receive_json_from()
        assert response[0] == "contact_request"
        contact_request_id = response[1]["id"]
        await c2.send_json_to(
            [
                "exhibition.contact_accept",
                123,
                {"contact_request": str(contact_request_id)},
            ]
        )
        response = await c2.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "exhibition.not_staff_member"
