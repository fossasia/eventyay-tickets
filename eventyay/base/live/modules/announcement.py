import logging

from venueless.core.permissions import Permission
from venueless.core.services.announcement import (
    create_announcement,
    get_announcement,
    get_announcements,
    update_announcement,
)
from venueless.live.channels import GROUP_WORLD
from venueless.live.decorators import command, event, require_world_permission
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class AnnouncementModule(BaseModule):
    prefix = "announcement"

    @command("create")
    @require_world_permission(Permission.WORLD_ANNOUNCE)
    async def create_announcement(self, body):
        announcement = await create_announcement(
            world=self.consumer.world,
            text=body.get("text"),
            show_until=body.get("show_until"),
            is_active=body.get("is_active"),
        )

        await self.consumer.send_success({"announcement": announcement})
        if announcement.pop("is_visible"):
            await self.consumer.channel_layer.group_send(
                GROUP_WORLD.format(id=self.consumer.world.id),
                {
                    "type": "announcement.created_or_updated",
                    "announcement": announcement,
                },
            )

    @command("update")
    @require_world_permission(Permission.WORLD_ANNOUNCE)
    async def update_announcement(self, body):
        old_announcement = await get_announcement(
            body.get("id"), world=self.consumer.world.id
        )
        new_announcement = await update_announcement(
            world=self.consumer.world.id, **body
        )

        await self.consumer.send_success({"announcement": new_announcement})

        if old_announcement.pop("is_visible") or new_announcement.pop("is_visible"):
            await self.consumer.channel_layer.group_send(
                GROUP_WORLD.format(id=self.consumer.world.id),
                {
                    "type": "announcement.created_or_updated",
                    "announcement": new_announcement,
                },
            )

    @command("list")
    @require_world_permission(Permission.WORLD_ANNOUNCE)
    async def list_announcements(self, body):
        announcements = []
        is_moderator = await self.consumer.world.has_permission_async(
            user=self.consumer.user,
            permission=Permission.WORLD_ANNOUNCE,
        )
        announcements = await get_announcements(
            world=self.consumer.world.id,
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
