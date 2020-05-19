import logging

from venueless.core.services.user import get_user
from venueless.core.services.world import get_world, get_world_config_for_user
from venueless.live.exceptions import ConsumerException

logger = logging.getLogger(__name__)


class WorldModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {}

    async def push_world_update(self):
        world_config = await get_world_config_for_user(
            await get_user(
                self.world_id, with_id=self.consumer.user.id, serialize=False
            )
        )
        await self.consumer.send_json(["world.updated", world_config])

    async def dispatch_event(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        if self.content["type"] == "world.update":
            await self.push_world_update()
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
