import re
import sys
from contextlib import asynccontextmanager

import pytest
from aioresponses import aioresponses
from channels.db import database_sync_to_async
from tests.utils import LoggingCommunicator

from venueless.core.models import User
from venueless.routing import application


@asynccontextmanager
async def world_communicator(client_id):
    communicator = LoggingCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": client_id}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    assert "world.config" in response[1], response
    await communicator.send_json_to(
        ["user.update", 123, {"profile": {"display_name": client_id}}]
    )
    await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_permission(world):
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ):
        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "error" == response[0]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_start_direct_channel(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2:
        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        assert "id" in response[2]
        assert "notification_pointer" in response[2]
        assert "state" in response[2]
        assert "a" in {a["profile"]["display_name"] for a in response[2]["members"]}
        assert "b" in {a["profile"]["display_name"] for a in response[2]["members"]}
        await c1.receive_json_from()  # join event
        await c1.receive_json_from()  # join event

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": response[2]["id"],
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        await c1.receive_json_from()

        response = await c2.receive_json_from()  # channel list
        assert response[0] == "chat.channels"
        assert "a" in {
            a["profile"]["display_name"] for a in response[1]["channels"][0]["members"]
        }
        assert "b" in {
            a["profile"]["display_name"] for a in response[1]["channels"][0]["members"]
        }
        await c2.receive_json_from()  # notification pointer


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_invalid_user(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1:
        await c1.send_json_to(
            ["chat.direct.create", 123, {"users": ["foobar"]},]
        )
        response = await c1.receive_json_from()
        assert "error" == response[0]


async def _setup_dms(c1, c2):
    await c1.send_json_to(
        [
            "chat.direct.create",
            123,
            {
                "users": [
                    str(
                        (
                            await database_sync_to_async(User.objects.get)(
                                client_id="b"
                            )
                        ).id
                    ),
                ]
            },
        ]
    )
    response = await c1.receive_json_from()
    assert "success" == response[0]
    channel = response[2]["id"]

    await c1.receive_json_from()  # join event 1
    await c1.receive_json_from()  # join event 2

    return channel


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_reuse_direct_channel(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2:
        channel = await _setup_dms(c1, c2)

        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        assert channel == response[2]["id"]

        await c2.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="a"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c2.receive_json_from()
        assert "success" == response[0]
        assert channel == response[2]["id"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_do_not_reuse_direct_channel_with_additional_user(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ), world_communicator(client_id="c"):
        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        ),
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="c"
                                )
                            ).id
                        ),
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        channel = response[2]["id"]

        await c1.receive_json_from()  # join event 1
        await c1.receive_json_from()  # join event 2
        await c1.receive_json_from()  # join event 3

        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        assert channel != response[2]["id"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscribe_member_only(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2, world_communicator(client_id="c") as c3:
        channel = await _setup_dms(c1, c2)

        await c1.send_json_to(
            ["chat.subscribe", 123, {"channel": channel},]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]

        await c3.send_json_to(
            ["chat.subscribe", 123, {"channel": channel},]
        )
        response = await c3.receive_json_from()
        assert "error" == response[0]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_member_only(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2, world_communicator(client_id="c") as c3:
        channel = await _setup_dms(c1, c2)

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": channel,
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]

        await c3.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": channel,
                },
            ]
        )
        response = await c3.receive_json_from()
        assert "error" == response[0]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_fetch_member_only(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2, world_communicator(client_id="c") as c3:
        channel = await _setup_dms(c1, c2)

        await c1.send_json_to(
            [
                "chat.fetch",
                123,
                {"channel": channel, "count": 20, "before_id": sys.maxsize,},
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]

        await c3.send_json_to(
            [
                "chat.fetch",
                123,
                {"channel": channel, "count": 20, "before_id": sys.maxsize,},
            ]
        )
        response = await c3.receive_json_from()
        assert "error" == response[0]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_blocked_user(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ):
        await c1.send_json_to(
            [
                "user.block",
                123,
                {
                    "id": str(
                        (
                            await database_sync_to_async(User.objects.get)(
                                client_id="b"
                            )
                        ).id
                    )
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "error" == response[0]
        assert "chat.denied" == response[2]["code"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_blocked_by_user(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2:
        await c2.send_json_to(
            [
                "user.block",
                123,
                {
                    "id": str(
                        (
                            await database_sync_to_async(User.objects.get)(
                                client_id="a"
                            )
                        ).id
                    )
                },
            ]
        )
        response = await c2.receive_json_from()
        assert "success" == response[0]
        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        )
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "error" == response[0]
        assert "chat.denied" == response[2]["code"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_if_blocked_by_user(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2:
        channel = await _setup_dms(c1, c2)
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": channel,
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]

        await c1.receive_json_from()  # chat event
        await c1.receive_json_from()  # new notification pointer
        await c2.receive_json_from()  # channel list
        await c2.receive_json_from()  # new notification pointer

        await c2.send_json_to(
            [
                "user.block",
                123,
                {
                    "id": str(
                        (
                            await database_sync_to_async(User.objects.get)(
                                client_id="a"
                            )
                        ).id
                    )
                },
            ]
        )
        response = await c2.receive_json_from()
        assert "success" == response[0]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": channel,
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "error" == response[0]
        assert "chat.denied" == response[2]["code"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_call_invite(world):
    with aioresponses() as m:
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

        world.trait_grants["participant"] = []
        await database_sync_to_async(world.save)()
        async with world_communicator(client_id="a") as c1, world_communicator(
            client_id="b"
        ) as c2:
            channel = await _setup_dms(c1, c2)
            await c1.send_json_to(
                [
                    "chat.send",
                    123,
                    {
                        "event_type": "channel.message",
                        "content": {"type": "call", "body": {}},
                        "channel": channel,
                    },
                ]
            )
            response = await c1.receive_json_from()
            assert "success" == response[0]

            response = await c1.receive_json_from()  # chat event
            await c1.receive_json_from()  # new notification pointer
            await c2.receive_json_from()  # new notification pointer

            assert response[0] == "chat.event"
            call_id = response[1]["content"]["body"]["id"]

            await c1.send_json_to(
                ["bbb.call_url", 123, {"call": call_id,},]
            )
            response = await c1.receive_json_from()
            assert "success" == response[0]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_send_call_require_invite(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2, world_communicator(client_id="c") as c3:
        channel = await _setup_dms(c1, c2)
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "call", "body": {}},
                    "channel": channel,
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]

        response = await c1.receive_json_from()  # chat event
        await c1.receive_json_from()  # new notification pointer
        await c2.receive_json_from()  # new notification pointer

        assert response[0] == "chat.event"
        call_id = response[1]["content"]["body"]["id"]

        await c3.send_json_to(
            ["bbb.call_url", 123, {"call": call_id,},]
        )
        response = await c3.receive_json_from()
        assert "error" == response[0]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_hide_and_reappear(world):
    world.trait_grants["participant"] = []
    await database_sync_to_async(world.save)()
    async with world_communicator(client_id="a") as c1, world_communicator(
        client_id="b"
    ) as c2, world_communicator(client_id="b") as c2b:
        await c2.receive_json_from()  # user updated

        await c1.send_json_to(
            [
                "chat.direct.create",
                123,
                {
                    "users": [
                        str(
                            (
                                await database_sync_to_async(User.objects.get)(
                                    client_id="b"
                                )
                            ).id
                        ),
                    ]
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        channel = response[2]["id"]

        await c1.receive_json_from()  # join event 1
        await c1.receive_json_from()  # join event ^2

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": channel,
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        await c1.receive_json_from()  # message
        await c1.receive_json_from()  # notification pointer

        cl = await c2.receive_json_from()  # channel list
        assert channel in [c["id"] for c in cl[1]["channels"]]
        await c2.receive_json_from()  # notification pointer

        await c2b.receive_json_from()  # channel list
        await c2b.receive_json_from()  # notification pointer

        await c2.send_json_to(
            ["chat.leave", 123, {"channel": channel},]
        )
        response = await c2.receive_json_from()
        assert "success" == response[0]
        cl = await c2b.receive_json_from()  # channel list
        assert channel not in [c["id"] for c in cl[1]["channels"]]

        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": "Hello world"},
                    "channel": channel,
                },
            ]
        )
        response = await c1.receive_json_from()
        assert "success" == response[0]
        await c1.receive_json_from()  # message

        cl = await c2.receive_json_from()  # channel list
        assert channel in [c["id"] for c in cl[1]["channels"]]
        await c2.receive_json_from()  # notification pointer
        await c2b.receive_json_from()  # channel list
        await c2b.receive_json_from()  # notification pointer
