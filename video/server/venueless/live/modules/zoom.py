import re

from django.core import signing
from django.urls import reverse

from venueless.core.permissions import Permission
from venueless.live.decorators import command, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule


class ZoomModule(BaseModule):
    prefix = "zoom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_ZOOM_JOIN,
        module_required="call.zoom",
    )
    async def room_url(self, body):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")

        data = signing.dumps(
            {
                "mn": int(
                    re.sub("[^0-9]", "", self.module_config.get("meeting_number"))
                ),
                "pw": self.module_config.get("password"),
                "un": self.consumer.user.profile.get("display_name"),
                "ho": bool(False),
                "ui": str(self.consumer.user.pk),
                "dc": self.module_config.get("disable_chat", False),
            }
        )
        url = f'//{self.consumer.world.domain}{reverse("zoom:meeting")}?data={data}'
        await self.consumer.send_success({"url": url})
