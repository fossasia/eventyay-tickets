import uuid
from contextlib import asynccontextmanager

import pytest
from channels.testing import WebsocketCommunicator

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
                    "description": "Ihr Partner im Großhandel",
                    "logo": "https://via.placeholder.com/150",
                    "size": 1,
                    "sorting_priority": 1,
                },
                {
                    "name": "Messebau Schmidt UG",
                    "description": "Handwerk aus Leidenschaft",
                    "logo": "https://via.placeholder.com/150",
                    "size": 1,
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
                "description": "Handwerk aus Leidenschaft",
                "logo": "https://via.placeholder.com/150",
                "text": "# Wir liefern wovon andere nur reden\n\nHallo!\nDas ist ein Markdowntext!",
                "header_img": "https://via.placeholder.com/728x90",
                "size": 1,
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
                "description": "Ihr Partner im Großhandel",
                "logo": "https://via.placeholder.com/150",
                "text": "# Gastro und mehr\n\nVon Apfel bis Zebra, wir liefern!",
                "header_img": "https://via.placeholder.com/728x90",
                "size": 1,
                "sorting_priority": 1,
                "links": [],
                "social_media_links": [
                    {"display_text": "linkedin", "url": "https://www.linkedin.com/"}
                ],
                "staff": [],
            },
        ]
