from venueless.core.permissions import Permission
from venueless.core.services.bbb import BBBService
from venueless.live.decorators import command, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule


class BBBModule(BaseModule):
    prefix = "bbb"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_BBB_JOIN,
        module_required="call.bigbluebutton",
    )
    async def room_url(self, body):
        service = BBBService(self.consumer.world)
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")
        url = await service.get_join_url_for_room(
            self.room,
            self.consumer.user,
            moderator=await self.consumer.world.has_permission_async(
                user=self.consumer.user,
                permission=Permission.ROOM_BBB_MODERATE,
                room=self.room,
            ),
        )
        if not url:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"url": url})

    @command("call_url")
    async def call_url(self, body):
        service = BBBService(self.consumer.world)
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")
        url = await service.get_join_url_for_call_id(
            body.get("call"),
            self.consumer.user,
        )
        if not url:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"url": url})

    @command("recordings")
    @room_action(
        permission_required=Permission.ROOM_BBB_RECORDINGS,
        module_required="call.bigbluebutton",
    )
    async def recordings(self, body):
        service = BBBService(self.consumer.world)
        recordings = await service.get_recordings_for_room(
            self.room,
        )
        await self.consumer.send_success({"results": recordings})
