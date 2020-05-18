import logging

from django.core.exceptions import ValidationError

from venueless.core.permissions import Permission
from venueless.core.services.user import get_user
from venueless.core.services.world import (
    create_room,
    get_room_config_for_user,
    get_world,
    get_world_config_for_user,
)
from venueless.live.decorators import require_world_permission
from venueless.live.exceptions import ConsumerException

logger = logging.getLogger(__name__)


class WorldModule:
    interactive = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            "room.create": self.create_room,
        }

    @require_world_permission(Permission.WORLD_ROOMS_CREATE)
    async def create_room(self):
        try:
            room = await create_room(self.world, self.content[-1], self.consumer.user)
        except ValidationError as e:
            await self.consumer.send_error(code="room.invalid", message=str(e))
        else:
            await self.consumer.send_success(room)

    async def push_world_update(self):
        world_config = await get_world_config_for_user(
            await get_user(
                self.world_id, with_id=self.consumer.user.id, serialize=False
            )
        )
        await self.consumer.send_json(["world.updated", world_config])

    async def push_room_info(self):
        world = await get_world(self.world_id)
        if not await world.has_permission_async(
            user=self.consumer.user, permission=Permission.ROOM_VIEW
        ):
            return
        await self.consumer.send_json(
            [
                self.content["type"],
                await get_room_config_for_user(
                    self.content["room"], self.world_id, self.consumer.user
                ),
            ]
        )

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        if self.content["type"] == "world.update":
            await self.push_world_update()
        if self.content["type"] == "room.create":
            await self.push_room_info()
        else:  # pragma: no cover
            logger.warning(
                f'Ignored unknown event {content["type"]}'
            )  # ignore unknown event

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world = await get_world(
            self.consumer.scope["url_route"]["kwargs"]["world"]
        )
        action = content[0]
        if action not in self.actions:
            raise ConsumerException("world.unsupported_command")
        await self.actions[action]()
