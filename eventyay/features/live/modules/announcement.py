import logging

from eventyay.core.permissions import Permission
from eventyay.base.services.announcement import (
    create_announcement,
    get_announcement,
    get_announcements,
    update_announcement,
)
from eventyay.features.live.channels import GROUP_EVENT
from eventyay.features.live.decorators import command, event, require_event_permission
from eventyay.features.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class AnnouncementModule(BaseModule):
    prefix = "announcement"

    @command("create")
    @require_event_permission(Permission.EVENT_ANNOUNCE)
    async def create_announcement(self, body):
        announcement = await create_announcement(
            event=self.consumer.event,
            text=body.get("text"),
            show_until=body.get("show_until"),
            is_active=body.get("is_active"),
        )

        await self.consumer.send_success({"announcement": announcement})
        if announcement.pop("is_visible"):
            await self.consumer.channel_layer.group_send(
                GROUP_EVENT.format(id=self.consumer.event.id),
                {
                    "type": "announcement.created_or_updated",
                    "announcement": announcement,
                },
            )

    @command("update")
    @require_event_permission(Permission.EVENT_ANNOUNCE)
    async def update_announcement(self, body):
        old_announcement = await get_announcement(
            body.get("id"), event=self.consumer.event.id
        )
        new_announcement = await update_announcement(
            event=self.consumer.event.id, **body
        )

        await self.consumer.send_success({"announcement": new_announcement})

        if old_announcement.pop("is_visible") or new_announcement.pop("is_visible"):
            await self.consumer.channel_layer.group_send(
                GROUP_EVENT.format(id=self.consumer.event.id),
                {
                    "type": "announcement.created_or_updated",
                    "announcement": new_announcement,
                },
            )

    @command("list")
    @require_event_permission(Permission.EVENT_ANNOUNCE)
    async def list_announcements(self, body):
        announcements = []
        is_moderator = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=Permission.EVENT_ANNOUNCE,
        )
        announcements = await get_announcements(
            event=self.consumer.event.id,
            moderator=is_moderator,
        )
        await self.consumer.send_success(announcements)

    @event("created_or_updated")
    async def push_announce(self, body):
        await self.consumer.send_json(
            [
                "announcement.created_or_updated",
                body.get("announcement"),
            ]
        )
