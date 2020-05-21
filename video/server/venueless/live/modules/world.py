import logging

from channels.db import database_sync_to_async

from venueless.core.services.world import get_world_config_for_user
from venueless.live.decorators import event
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class WorldModule(BaseModule):
    prefix = "world"

    @event("update", refresh_world=True, refresh_user=True)
    async def push_world_update(self, body):
        world_config = await database_sync_to_async(get_world_config_for_user)(
            self.consumer.world, self.consumer.user,
        )
        await self.consumer.send_json(["world.updated", world_config])
