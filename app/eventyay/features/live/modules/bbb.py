from eventyay.base.services.bbb import BBBServerUnavailable, BBBService
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


class BBBModule(BaseModule):
    prefix = "bbb"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _get_join_url(self, join_url):
        try:
            return await join_url
        except BBBServerUnavailable as exc:
            raise ConsumerException("bbb.failed") from exc

    async def can_moderate_room(self) -> bool:
        """
        Map Eventyay user moderation permissions to BBB moderator status.
        Checks if the user holds room moderation permission, or event/room
        administrative update rights.
        """
        return bool(
            await self.consumer.event.has_permission_async(
                user=self.consumer.user,
                permission=[
                    Permission.ROOM_BBB_MODERATE,
                    Permission.ROOM_UPDATE,
                    Permission.EVENT_UPDATE,
                ],
                room=self.room,
            )
        )

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_BBB_JOIN,
        module_required="call.bigbluebutton",
    )
    async def room_url(self, body):
        service = BBBService(self.consumer.event)
        display_name = (
            (self.consumer.user.profile or {}).get("display_name")
            or getattr(self.consumer.user, "fullname", None)
            or (self.consumer.user.email.split("@")[0] if getattr(self.consumer.user, "email", None) else None)
            or "Attendee"
        )
        if hasattr(self.consumer.user, "profile") and isinstance(self.consumer.user.profile, dict):
            if not self.consumer.user.profile.get("display_name"):
                self.consumer.user.profile["display_name"] = display_name
        elif not getattr(self.consumer.user, "profile", None):
            self.consumer.user.profile = {"display_name": display_name}
        is_moderator = await self.can_moderate_room()
        url = await self._get_join_url(
            service.get_join_url_for_room(
                self.room,
                self.consumer.user,
                moderator=is_moderator,
            )
        )

        if not url:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"url": url})

    @command("call_url")
    async def call_url(self, body):
        service = BBBService(self.consumer.event)
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")
        url = await self._get_join_url(
            service.get_join_url_for_call_id(
                body.get("call"),
                self.consumer.user,
            )
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
        service = BBBService(self.consumer.event)
        recordings = await service.get_recordings_for_room(
            self.room,
        )
        if recordings is None:
            raise ConsumerException("bbb.failed")
        await self.consumer.send_success({"results": recordings})
