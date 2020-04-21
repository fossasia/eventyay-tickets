import uuid
from contextlib import asynccontextmanager

import pytest
from aiohttp.http_exceptions import HttpProcessingError
from aioresponses import aioresponses
from channels.testing import WebsocketCommunicator

from stayseated.routing import application


@asynccontextmanager
async def world_communicator(named=True):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    assert "world.config" in response[1], response
    if named:
        await communicator.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_settings_not_disclosed():
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    assert response[1]["world.config"]["rooms"][1]["id"] == "room_1"
    assert (
        response[1]["world.config"]["rooms"][1]["modules"][0]["type"]
        == "call.bigbluebutton"
    )
    assert response[1]["world.config"]["rooms"][1]["modules"][0]["config"] == {}
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_command():
    async with world_communicator() as c:
        await c.send_json_to(["bbb.bla", 123, {"room": "room_0"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "bbb.unsupported_command"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_room():
    async with world_communicator() as c:
        await c.send_json_to(["bbb.url", 123, {"room": "room_0"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "bbb.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unknown_room():
    async with world_communicator() as c:
        await c.send_json_to(["bbb.url", 123, {"room": "a"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "room.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unnamed():
    async with world_communicator(named=False) as c:
        await c.send_json_to(["bbb.url", 123, {"room": "room_1"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "bbb.join.missing_profile"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_down():
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.url", 123, {"room": "room_1"}])

            m.get(
                "https://video1.pretix.eu/bigbluebutton/api/create?attendeePW=311584b1c1e46e53&checksum"
                "=b1e852b960e25b6ac2e2513fd3335c2e3b3b03f3&meetingID=2aa5179961ef81eb&meta_Room=room_1&meta_Source"
                "=stayseated&meta_World=sample&moderatorPW=6887ebdc87b802d0&name=Gruppenraum+1&record=false",
                status=500,
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_exception():
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.url", 123, {"room": "room_1"}])

            m.get(
                "https://video1.pretix.eu/bigbluebutton/api/create?attendeePW=311584b1c1e46e53&checksum"
                "=b1e852b960e25b6ac2e2513fd3335c2e3b3b03f3&meetingID=2aa5179961ef81eb&meta_Room=room_1&meta_Source"
                "=stayseated&meta_World=sample&moderatorPW=6887ebdc87b802d0&name=Gruppenraum+1&record=false",
                exception=HttpProcessingError(),
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_xml_error():
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.url", 123, {"room": "room_1"}])

            m.get(
                "https://video1.pretix.eu/bigbluebutton/api/create?attendeePW=311584b1c1e46e53&checksum"
                "=b1e852b960e25b6ac2e2513fd3335c2e3b3b03f3&meetingID=2aa5179961ef81eb&meta_Room=room_1&meta_Source"
                "=stayseated&meta_World=sample&moderatorPW=6887ebdc87b802d0&name=Gruppenraum+1&record=false",
                body="""<response>
<returncode>FAILED</returncode>
<messageKey>checksumError</messageKey>
<message>You did not pass the checksum security check</message>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_successful_url():
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.url", 123, {"room": "room_1"}])

            m.get(
                "https://video1.pretix.eu/bigbluebutton/api/create?attendeePW=311584b1c1e46e53&checksum"
                "=b1e852b960e25b6ac2e2513fd3335c2e3b3b03f3&meetingID=2aa5179961ef81eb&meta_Room=room_1&meta_Source"
                "=stayseated&meta_World=sample&moderatorPW=6887ebdc87b802d0&name=Gruppenraum+1&record=false",
                body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>6c58284d0c68af95</meetingID>
<internalMeetingID>322ed97cafe9a92fa4ef7f7c70da553f213df06b-1587484839039</internalMeetingID>
<parentMeetingID>bbb-none</parentMeetingID>
<attendeePW>d35746f043310256</attendeePW>
<moderatorPW>bf889e3c60742bee</moderatorPW>
<createTime>1587484839039</createTime>
<voiceBridge>70957</voiceBridge>
<dialNumber>613-555-1234</dialNumber>
<createDate>Tue Apr 21 18:00:39 CEST 2020</createDate>
<hasUserJoined>true</hasUserJoined>
<duration>0</duration>
<hasBeenForciblyEnded>false</hasBeenForciblyEnded>
<messageKey>duplicateWarning</messageKey>
<message>
This conference was already in existence and may currently be in progress.
</message>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert response[2] == {
                "url": (
                    "https://video1.pretix.eu/bigbluebutton/api/join?meetingID=2aa5179961ef81eb&fullName=Foo"
                    "+Fighter&password=311584b1c1e46e53&joinViaHtml5=true&checksum"
                    "=12288c016f7255aa75b7b9b280e8b3e00387eaba"
                )
            }
