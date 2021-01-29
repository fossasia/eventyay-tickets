import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from venueless.core.models import Exhibitor, ExhibitorStaff, User
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
                    "banner_list": None,
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
                    "banner_list": None,
                    "sorting_priority": 0,
                },
            ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_list_all(world, exhibition_room):
    async with world_communicator() as c:
        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )
        await c.send_json_to(["exhibition.list.all", 123, {}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        for e in response[2]["exhibitors"]:
            del e["id"]
            assert e in [
                {
                    "name": "Tube GmbH",
                },
                {
                    "name": "Messebau Schmidt UG",
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
                "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod"
                " tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero "
                "eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea tak",
                "logo": "https://via.placeholder.com/150",
                "banner_list": None,
                "banner_detail": None,
                "contact_enabled": True,
                "text_legacy": "# Wir liefern wovon andere nur reden\n\nHallo!\nDas ist ein Markdowntext!",
                "text_content": [],
                "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod "
                "tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero "
                "eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea tak",
                "size": "1x1",
                "sorting_priority": 0,
                "highlighted_room_id": None,
                "links": [
                    {
                        "display_text": "Website",
                        "url": "http://example.org/",
                        "category": "profile",
                    },
                    {
                        "display_text": "Info Broschüre",
                        "url": "https://de.wikipedia.org/wiki/Messebau",
                        "category": "profile",
                    },
                ],
                "social_media_links": [
                    {"display_text": "XING", "url": "https://www.xing.com/"}
                ],
                "staff": [],
                "room_id": str(exhibition_room.pk),
            },
            {
                "name": "Tube GmbH",
                "tagline": "Ihr Partner im Großhandel",
                "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod "
                "tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero "
                "eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea tak",
                "logo": "https://via.placeholder.com/150",
                "banner_list": None,
                "banner_detail": None,
                "contact_enabled": True,
                "text_legacy": "# Gastro und mehr\n\nVon Apfel bis Zebra, wir liefern!",
                "text_content": [],
                "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod "
                "tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero "
                "eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea tak",
                "size": "1x1",
                "sorting_priority": 1,
                "highlighted_room_id": None,
                "links": [],
                "social_media_links": [
                    {"display_text": "linkedin", "url": "https://www.linkedin.com/"}
                ],
                "staff": [],
                "room_id": str(exhibition_room.pk),
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
async def test_staffed_by_user(world, exhibition_room):
    async with world_communicator() as c:
        await c.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c.receive_json_from()
        e_id = response[2]["exhibitors"].pop()["id"]

        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )
        await c.send_json_to(
            [
                "exhibition.add_staff",
                123,
                {
                    "exhibitor": str(e_id),
                    "user": str(c.context["user.config"]["id"]),
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"

        await c.send_json_to(
            [
                "exhibition.get.staffed_by_user",
                123,
                {"user_id": str(c.context["user.config"]["id"])},
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["exhibitors"][0]["id"] == e_id


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_contact_cancel(world, exhibition_room):
    async with world_communicator() as c_staff, world_communicator() as c1:
        await database_sync_to_async(world.world_grants.create)(
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
        assert response[2]["exhibitor"]["staff"][0]["id"] == str(
            c_staff.context["user.config"]["id"]
        )

        # issue contact request
        await c1.send_json_to(["exhibition.contact", 123, {"exhibitor": str(e["id"])}])
        response = await c1.receive_json_from()
        assert response[0] == "success"
        request_id = response[2]["contact_request"]["id"]

        response = await c_staff.receive_json_from()
        assert response[0] == "exhibition.contact_request"
        assert response[1]["contact_request"]["id"] == request_id

        await c1.send_json_to(
            ["exhibition.contact_cancel", 123, {"contact_request": request_id}]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        response = await c_staff.receive_json_from()
        assert response[0] == "exhibition.contact_request_close"
        assert response[1]["contact_request"]["id"] == request_id


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_contact(world, exhibition_room):
    async with world_communicator() as c_staff, world_communicator() as c1:
        await database_sync_to_async(world.world_grants.create)(
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
        assert response[2]["exhibitor"]["staff"][0]["id"] == str(
            c_staff.context["user.config"]["id"]
        )

        # issue contact request
        await c1.send_json_to(
            [
                "exhibition.contact",
                123,
                {"exhibitor": str(e["id"])},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        # receive request and answer
        response = await c_staff.receive_json_from()
        assert response[0] == "exhibition.contact_request"
        contact_request_id = response[1]["contact_request"]["id"]
        await c_staff.send_json_to(
            [
                "exhibition.contact_accept",
                123,
                {
                    "contact_request": str(contact_request_id),
                    "channel": "can_also_be_fake_here",
                },
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "success"
        response = await c1.receive_json_from()
        assert response[0] == "exhibition.contact_accepted"
        assert response[1]["contact_request"]["answered_by"]["id"] == str(
            c_staff.context["user.config"]["id"]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "exhibition.contact_request_close"

        # try to answer same request twice
        await c_staff.send_json_to(
            [
                "exhibition.contact_accept",
                123,
                {
                    "contact_request": str(contact_request_id),
                    "channel": "can_also_be_fake_here",
                },
            ]
        )
        response = await c_staff.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "exhibition.unknown_contact_request"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_contact_not_staff(world, exhibition_room):
    async with world_communicator() as c_staff, world_communicator() as c1, world_communicator() as c2:
        await database_sync_to_async(world.world_grants.create)(
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
        assert response[2]["exhibitor"]["staff"][0]["id"] == str(
            c_staff.context["user.config"]["id"]
        )

        # issue contact request
        await c1.send_json_to(
            [
                "exhibition.contact",
                123,
                {"exhibitor": str(e["id"])},
            ]
        )
        response = await c1.receive_json_from()
        assert response[0] == "success"

        # receive request and answer
        response = await c_staff.receive_json_from()
        assert response[0] == "exhibition.contact_request"
        contact_request_id = response[1]["contact_request"]["id"]
        await c2.send_json_to(
            [
                "exhibition.contact_accept",
                123,
                {
                    "contact_request": str(contact_request_id),
                    "channel": "can_also_be_fake_here",
                },
            ]
        )
        response = await c2.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "exhibition.not_staff_member"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_delete(world, exhibition_room):
    async with world_communicator() as c:
        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )

        await c.send_json_to(
            ["exhibition.list", 123, {"room": str(exhibition_room.pk)}]
        )
        response = await c.receive_json_from()
        assert response[0] == "success"
        e = response[2]["exhibitors"][0]

        await c.send_json_to(["exhibition.delete", 123, {"exhibitor": str(e["id"])}])
        response = await c.receive_json_from()
        assert response[0] == "success"

        await c.send_json_to(["exhibition.delete", 123, {"exhibitor": str(e["id"])}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "exhibition.unknown_exhibitor"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_patch(world, exhibition_room):
    async with world_communicator() as c:
        await database_sync_to_async(world.world_grants.create)(
            user=await database_sync_to_async(User.objects.get)(
                id=c.context["user.config"]["id"]
            ),
            world=world,
            role="admin",
        )

        e = {
            "id": "",
            "name": "Test Aussteller",
            "tagline": "Look at me: still talking, when there's science to do",
            "short_text": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt.",
            "text_legacy": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut "
            "labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea "
            "rebum.",
            "text_content": [],
            "size": "3x3",
            "sorting_priority": 4,
            "logo": "https://via.placeholder.com/150",
            "banner_list": "https://via.placeholder.com/260x130",
            "banner_detail": "https://via.placeholder.com/720x360",
            "contact_enabled": True,
            "room_id": str(exhibition_room.pk),
            "highlighted_room_id": None,
            "social_media_links": [],
            "links": [],
            "staff": [],
        }

        await c.send_json_to(["exhibition.patch", 123, e])
        response = await c.receive_json_from()
        assert response[0] == "success"
        e["id"] = response[2]["exhibitor"]["id"]
        assert response[2]["exhibitor"] == e

        e["name"] = "Test Aussteller GmbH"
        await c.send_json_to(["exhibition.patch", 123, e])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["exhibitor"] == e


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_exhibition_patch_as_staff(world, exhibition_room):
    async with world_communicator() as c:
        user = await database_sync_to_async(User.objects.get)(
            id=c.context["user.config"]["id"]
        )
        exhibitor = await database_sync_to_async(Exhibitor.objects.get)(
            name="Tube GmbH"
        )
        await database_sync_to_async(ExhibitorStaff.objects.create)(
            exhibitor=exhibitor,
            user=user,
        )

        e = {
            "id": str(exhibitor.id),
            "name": "Name will be kept",
            "room": "invalid",
            "size": "3x3",
            "sorting_priority": -30,
            "logo": "https://example.org",
            "staff": [],
        }

        await c.send_json_to(["exhibition.patch", 123, e])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["exhibitor"]["name"] == "Tube GmbH"
        assert response[2]["exhibitor"]["room_id"] == str(exhibition_room.id)
        assert response[2]["exhibitor"]["size"] == "1x1"
        assert response[2]["exhibitor"]["sorting_priority"] != -30
        assert response[2]["exhibitor"]["logo"] == "https://example.org"
        assert len(response[2]["exhibitor"]["staff"]) >= 1
