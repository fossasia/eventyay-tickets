from venueless.core.permissions import Permission
from venueless.core.services.bbb import BBBService
from venueless.core.services.world import get_world
from venueless.live.decorators import room_action
from venueless.live.exceptions import ConsumerException


class BBBModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            "url": self.url,
        }

    @room_action(
        permission_required=Permission.ROOM_BBB_JOIN,
        module_required="call.bigbluebutton",
    )
    async def url(self):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")
        url = await self.service.get_join_url(
            self.room,
            self.consumer.user.profile.get("display_name"),
            moderator=await self.world.has_permission_async(
                user=self.consumer.user,
                permission=Permission.ROOM_BBB_MODERATE,
                room=self.room,
            ),
        )
        if not url:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"url": url})

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.room_id = self.content[2].get("room")
        self.world_id = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.world = await get_world(self.world_id)
        self.service = BBBService(self.world_id)
        _, action = content[0].rsplit(".", maxsplit=1)
        if action not in self.actions:
            raise ConsumerException("bbb.unsupported_command")
        await self.actions[action]()
