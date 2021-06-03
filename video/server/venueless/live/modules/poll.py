import logging

from venueless.core.models.poll import Poll
from venueless.core.permissions import Permission
from venueless.core.services.poll import (
    create_poll,
    delete_poll,
    get_poll,
    get_polls,
    pin_poll,
    update_poll,
    vote_on_poll,
)
from venueless.live.channels import (
    GROUP_ROOM_POLL_MANAGE,
    GROUP_ROOM_POLL_READ,
    GROUP_ROOM_POLL_RESULTS,
)
from venueless.live.decorators import command, event, room_action
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class PollModule(BaseModule):
    prefix = "poll"

    def get_group_for_state(self, state):
        return (
            GROUP_ROOM_POLL_MANAGE
            if state in (Poll.States.DRAFT, Poll.States.ARCHIVED)
            else GROUP_ROOM_POLL_READ
        ).format(id=self.room.pk)

    @command("create")
    @room_action(
        permission_required=Permission.ROOM_POLL_MANAGE, module_required="poll"
    )
    async def create_poll(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("poll.inactive")
            return

        poll = await create_poll(
            room=self.room,
            content=body.get("content"),
            options=body.get("options"),
            state=body.get("state"),
            poll_type=body.get("poll_type"),
        )

        await self.consumer.send_success({"poll": poll})
        group = self.get_group_for_state(poll["state"])
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "poll.created_or_updated",
                "room": str(self.room.pk),
                "poll": poll,
            },
        )

    @command("update")
    @room_action(
        permission_required=Permission.ROOM_POLL_MANAGE,
        module_required="poll",
    )
    async def update_poll(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("poll.inactive")
            return

        await get_poll(body.get("id"), self.room)  # make sure poll exists
        body["room"] = self.room
        new_poll = await update_poll(**body)

        await self.consumer.send_success({"poll": new_poll})

        group = self.get_group_for_state(new_poll["state"])
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "poll.created_or_updated",
                "room": str(self.room.pk),
                "poll": new_poll,
            },
        )

    @command("delete")
    @room_action(
        permission_required=Permission.ROOM_POLL_MANAGE,
        module_required="poll",
    )
    async def delete_poll(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("poll.inactive")
            return
        old_poll = await get_poll(body.get("id"), self.room)
        await delete_poll(id=old_poll["id"], room=self.room)
        await self.consumer.send_success({"poll": old_poll["id"]})
        group = self.get_group_for_state(old_poll["state"])
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "poll.deleted",
                "room": str(self.room.pk),
                "id": old_poll["id"],
            },
        )

    @command("vote")
    @room_action(permission_required=Permission.ROOM_POLL_VOTE, module_required="poll")
    async def vote(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("poll.inactive")
            return

        try:
            poll = await vote_on_poll(
                room=body.get("room"),
                pk=body.get("id"),
                user=self.consumer.user,
                options=body.get("options", []),
            )
        except Exception as e:
            await self.consumer.send_error("poll.vote", message=str(e))
            return

        await self.consumer.send_success({"poll": poll})

        poll_results = GROUP_ROOM_POLL_RESULTS.format(id=self.room.pk, poll=poll["id"])
        await self.consumer.channel_layer.group_add(
            poll_results, self.consumer.channel_name
        )

        await self.consumer.channel_layer.group_send(
            GROUP_ROOM_POLL_MANAGE.format(id=self.room.pk),
            {
                "type": "poll.created_or_updated",
                "room": str(self.room.pk),
                "poll": poll,
            },
        )
        await self.consumer.channel_layer.group_send(
            poll_results.format(id=self.room.pk, poll=poll["id"]),
            {
                "type": "poll.created_or_updated",
                "room": str(self.room.pk),
                "poll": poll,
            },
        )

    @command("list")
    @room_action(permission_required=Permission.ROOM_POLL_READ, module_required="poll")
    async def list_polls(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("poll.inactive")
            return

        polls = []
        is_moderator = await self.consumer.world.has_permission_async(
            user=self.consumer.user,
            room=self.room,
            permission=Permission.ROOM_POLL_MANAGE,
        )
        polls = await get_polls(
            room=self.room.id,
            for_user=self.consumer.user,
            moderator=is_moderator,
        )
        await self.consumer.send_success(polls)

    @command("pin")
    @room_action(permission_required=Permission.ROOM_POLL_MANAGE)
    async def pin_poll(self, body):
        poll = await get_poll(body.get("id"), self.room)
        await pin_poll(pk=poll["id"], room=self.room)
        await self.consumer.send_success({"id": str(poll["id"])})
        group = self.get_group_for_state(poll["state"])
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "poll.pinned",
                "room": str(self.room.pk),
                "id": poll["id"],
            },
        )

    @event("created_or_updated")
    async def push_poll(self, body):
        await self.consumer.send_json(
            ["poll.created_or_updated", {"poll": body.get("poll")}]
        )

    @event("deleted")
    async def push_delete(self, body):
        await self.consumer.send_json(
            [
                "poll.deleted",
                {"room": body.get("room"), "id": body.get("id")},
            ]
        )

    @event("pinned")
    async def push_pin(self, body):
        await self.consumer.send_json(
            [
                "poll.pinned",
                {"room": body.get("room"), "id": body.get("id")},
            ]
        )
