from venueless.core.permissions import Permission
from venueless.core.services.bbb import BBBService
from venueless.live.decorators import command, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule


class BBBModule(BaseModule):
    prefix = "bbb"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @command("url")
    @room_action(
        permission_required=Permission.ROOM_BBB_JOIN,
        module_required="call.bigbluebutton",
    )
    async def url(self, body):
        service = BBBService(self.consumer.world.id)
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")
        url = await service.get_join_url(
            self.room,
            self.consumer.user.profile.get("display_name"),
            moderator=await self.consumer.world.has_permission_async(
                user=self.consumer.user,
                permission=Permission.ROOM_BBB_MODERATE,
                room=self.room,
            ),
        )
        if not url:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"url": url})
