from stayseated.core.services.bbb import BBBService
from stayseated.core.services.world import get_room_config
from stayseated.live.exceptions import ConsumerException


class BBBModule:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            "url": self.url,
        }

    async def get_room(self):
        room_config = await get_room_config(self.world, self.room_id)
        if not room_config:
            raise ConsumerException("room.unknown", "Unknown room ID")
        if "call.bigbluebutton" not in [m["type"] for m in room_config["modules"]]:
            raise ConsumerException("bbb.unknown", "Room does not contain a BBB room.")
        return room_config

    async def url(self):
        room = await self.get_room()
        # TODO: Check permissions, assign moderator permission
        if not self.consumer.user.get("profile", {}).get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")
        url = await self.service.get_join_url(
            room,
            self.consumer.user.get("profile", {}).get("display_name"),
            moderator=False,
        )
        if not url:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"url": url})

    async def dispatch_command(self, consumer, content):
        self.consumer = consumer
        self.content = content
        self.room_id = self.content[2].get("room")
        self.world = self.consumer.scope["url_route"]["kwargs"]["world"]
        self.service = BBBService(self.world)
        _, action = content[0].rsplit(".", maxsplit=1)
        if action not in self.actions:
            raise ConsumerException("bbb.unsupported_command")
        await self.actions[action]()
