import asyncio
import uuid

import pytest
from channels.db import database_sync_to_async

from tests.live.test_chat import world_communicator
from tests.utils import get_token
from venueless.core.models import User

# Tests on notification handling accross clients are in test_chat_direct, so we test mostly the mention parsing here


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_notification_on_mention_if_joined(world, chat_room):
    sender_token = get_token(world, [], uid="a")
    receiver_token = get_token(world, [], uid="b")
    channel_id = str(chat_room.channel.id)
    async with world_communicator(token=sender_token) as c1, world_communicator(
        token=receiver_token
    ) as c2:
        # Setup. Both clients join, then c2 unsubscribes again ("background tab")
        await c1.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c1.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c1

        await c2.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c2.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c2
        await c2.receive_json_from()  # Join notification c2

        await c2.send_json_to(["chat.unsubscribe", 123, {"channel": channel_id}])
        await c2.receive_json_from()  # Success

        user_b = await database_sync_to_async(User.objects.get)(token_id="b")

        # c1 sends a message
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": f"Hello @{user_b.pk}"},
                },
            ]
        )
        await c1.receive_json_from()  # success
        await c1.receive_json_from()  # receives message back

        # c2 gets a notification
        response = await c2.receive_json_from()
        assert response[0] == "chat.notification"
        assert channel_id == response[1]["event"]["channel"]

        # c2 gets an unread pointer
        response = await c2.receive_json_from()
        assert response[0] == "chat.unread_pointers"
        assert channel_id in response[1]

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()  # no message to either client
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()  # no message to either client


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_notification_on_mention_if_rate_limit_exceeded(world, chat_room):
    sender_token = get_token(world, [], uid="a")
    receiver_token = get_token(world, [], uid="b")
    channel_id = str(chat_room.channel.id)
    async with world_communicator(token=sender_token) as c1, world_communicator(
        token=receiver_token
    ) as c2:
        # Setup. Both clients join, then c2 unsubscribes again ("background tab")
        await c1.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c1.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c1

        await c2.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c2.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c2
        await c2.receive_json_from()  # Join notification c2

        await c2.send_json_to(["chat.unsubscribe", 123, {"channel": channel_id}])
        await c2.receive_json_from()  # Success

        user_b = await database_sync_to_async(User.objects.get)(token_id="b")

        # c1 sends a message
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "content": {
                        "type": "text",
                        "body": f"Hello @{user_b.pk} "
                        + " ".join([f"@{uuid.uuid4()}" for i in range(60)]),
                    },
                },
            ]
        )
        await c1.receive_json_from()  # success
        await c1.receive_json_from()  # receives message back

        # c2 gets an unread pointer
        response = await c2.receive_json_from()
        assert response[0] == "chat.unread_pointers"
        assert channel_id in response[1]

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()  # no message to either client
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()  # no message to either client


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_notification_on_mention_if_not_joined(world, chat_room):
    sender_token = get_token(world, [], uid="a")
    receiver_token = get_token(world, [], uid="b")
    channel_id = str(chat_room.channel.id)
    async with world_communicator(token=sender_token) as c1, world_communicator(
        token=receiver_token
    ) as c2:
        await c1.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c1.receive_json_from()  # Success
        await c1.receive_json_from()  # Join notification c1

        user_b = await database_sync_to_async(User.objects.get)(token_id="b")

        # c1 sends a message
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": f"Hello @{user_b.pk}"},
                },
            ]
        )
        assert "success" == (await c1.receive_json_from())[0]
        assert "chat.mention_warning" == (await c1.receive_json_from())[0]
        assert "chat.event" == (await c1.receive_json_from())[0]

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()  # no message to either client
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()  # no message to either client


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_notification_on_mention_if_not_joined_volatile_and_permitted(
    world, volatile_chat_room
):
    sender_token = get_token(world, [], uid="a")
    receiver_token = get_token(world, [], uid="b")
    channel_id = str(volatile_chat_room.channel.id)
    async with world_communicator(token=sender_token) as c1, world_communicator(
        token=receiver_token
    ) as c2:
        # Setup. Both clients join, then c2 unsubscribes again ("background tab")
        await c1.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c1.receive_json_from()  # Success

        user_b = await database_sync_to_async(User.objects.get)(token_id="b")

        # c1 sends a message
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": f"Hello @{user_b.pk}"},
                },
            ]
        )
        await c1.receive_json_from()  # success
        await c1.receive_json_from()  # receives message back

        # c2 gets a notification
        response = await c2.receive_json_from()
        assert response[0] == "chat.notification"
        assert channel_id == response[1]["event"]["channel"]

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()  # no message to either client
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()  # no message to either client


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_notification_on_mention_if_not_joined_volatile_and_no_permitted(
    world, volatile_chat_room
):
    volatile_chat_room.trait_grants = {"participant": ["foo"]}
    await database_sync_to_async(volatile_chat_room.save)()
    sender_token = get_token(world, ["foo"], uid="a")
    receiver_token = get_token(world, [], uid="b")
    channel_id = str(volatile_chat_room.channel.id)
    async with world_communicator(token=sender_token) as c1, world_communicator(
        token=receiver_token
    ) as c2:
        # Setup. Both clients join, then c2 unsubscribes again ("background tab")
        await c1.send_json_to(["chat.join", 123, {"channel": channel_id}])
        await c1.receive_json_from()  # Success

        user_b = await database_sync_to_async(User.objects.get)(token_id="b")

        # c1 sends a message
        await c1.send_json_to(
            [
                "chat.send",
                123,
                {
                    "channel": channel_id,
                    "event_type": "channel.message",
                    "content": {"type": "text", "body": f"Hello @{user_b.pk}"},
                },
            ]
        )
        assert "success" == (await c1.receive_json_from())[0]
        assert "chat.mention_warning" == (await c1.receive_json_from())[0]
        assert "chat.event" == (await c1.receive_json_from())[0]

        with pytest.raises(asyncio.TimeoutError):
            await c1.receive_json_from()  # no message to either client
        with pytest.raises(asyncio.TimeoutError):
            await c2.receive_json_from()  # no message to either client
