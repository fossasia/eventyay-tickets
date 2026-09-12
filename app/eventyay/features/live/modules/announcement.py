import logging

from eventyay.base.services.announcement import (
    create_announcement,
    get_announcement,
    get_announcements,
    update_announcement,
)
from eventyay.core.permissions import Permission
from eventyay.features.live.channels import GROUP_EVENT
from eventyay.features.live.decorators import command, event, require_event_permission
from eventyay.features.live.modules.base import BaseModule


logger = logging.getLogger(__name__)


def is_announcements_enabled(event) -> bool:
    """Return True if announcements feature is enabled for the event (default False)."""
    config = getattr(event, "config", None) or {}
    if not isinstance(config, dict):
        return False
    live_features = config.get("live_features") or {}
    if not isinstance(live_features, dict):
        return False
    return bool(live_features.get("announcements", False))


class AnnouncementModule(BaseModule):
    prefix = "announcement"

    @command("create")
    @require_event_permission(Permission.EVENT_ANNOUNCE)
    async def create_announcement(self, body):
        if not is_announcements_enabled(self.consumer.event):
            await self.consumer.send_error(code="announcements.disabled")
            return

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
        if not is_announcements_enabled(self.consumer.event):
            await self.consumer.send_error(code="announcements.disabled")
            return

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
        if not is_announcements_enabled(self.consumer.event):
            await self.consumer.send_error(code="announcements.disabled")
            return

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
        if not is_announcements_enabled(self.consumer.event):
            return
        await self.consumer.send_json(
            [
                "announcement.created_or_updated",
                body.get("announcement"),
            ]
        )
