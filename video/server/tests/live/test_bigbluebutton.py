import re
import uuid
from contextlib import asynccontextmanager

import pytest
from aiohttp.http_exceptions import HttpProcessingError
from aioresponses import aioresponses
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from venueless.core.models import User
from venueless.routing import application


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
async def test_settings_not_disclosed(bbb_room):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    assert "bbb_defaults" not in response[1]["world.config"]["world"]
    for room in response[1]["world.config"]["rooms"]:
        if room["id"] == str(bbb_room.id):
            assert room["modules"][0]["type"] == "call.bigbluebutton"
            assert room["modules"][0]["config"] == {}
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_login_required(bbb_room):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        await communicator.send_json_to(
            ["bbb.room_url", 123, {"room": str(bbb_room.pk)}]
        )
        response = await communicator.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.unauthenticated"
    finally:
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
async def test_wrong_room(chat_room):
    async with world_communicator() as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": str(chat_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "room.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unknown_room():
    async with world_communicator() as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": "a"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "room.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unnamed(bbb_room):
    async with world_communicator(named=False) as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "bbb.join.missing_profile"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_missing_permission(bbb_room):
    bbb_room.trait_grants = {"participant": ["foo"]}
    await database_sync_to_async(bbb_room.save)()
    async with world_communicator(named=False) as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.denied"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_silenced(bbb_room):
    await database_sync_to_async(bbb_room.save)()
    async with world_communicator(named=False) as c:
        user = await database_sync_to_async(User.objects.get)()
        user.moderation_state = User.ModerationState.SILENCED
        await database_sync_to_async(user.save)()
        await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.denied"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_down(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])

            m.get(re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"), status=500)

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_exception(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
                exception=HttpProcessingError(),
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_xml_error(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
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
async def test_successful_url(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
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
            assert "/join?" in response[2]["url"]

            @database_sync_to_async
            def get_call():
                return bbb_room.bbb_call

            assert (await get_call()).attendee_pw in response[2]["url"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_successful_url_moderator(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await database_sync_to_async(bbb_room.role_grants.create)(
                user=await database_sync_to_async(User.objects.get)(),
                world=bbb_room.world,
                role="speaker",
            )
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
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
            assert "/join?" in response[2]["url"]

            @database_sync_to_async
            def get_call():
                return bbb_room.bbb_call

            assert (await get_call()).moderator_pw in response[2]["url"]
