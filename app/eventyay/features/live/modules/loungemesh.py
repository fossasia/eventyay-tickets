import logging

from channels.db import database_sync_to_async
from django_scopes import scope

from eventyay.base.services.loungemesh import (
    get_loungemesh_server,
    issue_join_url,
    loungemesh_is_available,
)
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class LoungeMeshModule(BaseModule):
    prefix = "loungemesh"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @database_sync_to_async
    def _get_join_url(self, is_moderator):
        with scope(event=self.consumer.event):
            room = getattr(self, "room", None)
            if not room:
                return None
            prefer_server = (self.module_config or {}).get("prefer_server")
            server = get_loungemesh_server(self.consumer.event, prefer_server=prefer_server)
            if not server:
                return None
            return issue_join_url(
                self.consumer.event,
                room,
                self.consumer.user,
                moderator=is_moderator,
                server=server,
            )

    async def can_moderate_room(self) -> bool:
        return bool(
            await self.consumer.event.has_permission_async(
                user=self.consumer.user,
                permission=[
                    Permission.ROOM_LOUNGEMESH_MODERATE,
                    Permission.ROOM_UPDATE,
                    Permission.EVENT_UPDATE,
                ],
                room=self.room,
            )
        )

    @command("room_url")
    @room_action(
        permission_required=[
            Permission.ROOM_LOUNGEMESH_JOIN,
            Permission.ROOM_UPDATE,
            Permission.EVENT_UPDATE,
        ],
        module_required="call.loungemesh",
    )
    async def room_url(self, body):
        is_moderator = await self.can_moderate_room()
        url = await self._get_join_url(is_moderator)
        if not url:
            raise ConsumerException("loungemesh.unavailable", "No LoungeMesh server available.")
        await self.consumer.send_success({"url": url, "moderator": is_moderator})
