import logging

from venueless.core.services.exhibition import ExhibitionService
from venueless.live.decorators import command, room_action
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class ExhibitionModule(BaseModule):
    prefix = "exhibition"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = ExhibitionService(self.consumer.world.id)

    @command("list")
    @room_action(module_required="exhibition.native")
    async def list(self, body):
        exhibitors = await self.service.get_exhibitors(room_id=body["room"])
        await self.consumer.send_success({"exhibitors": exhibitors})
