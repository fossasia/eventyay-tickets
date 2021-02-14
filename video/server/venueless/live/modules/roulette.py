from venueless.core.permissions import Permission
from venueless.core.services.roulette import (
    is_member_of_roulette_call,
    roulette_cleanup,
    roulette_request,
)
from venueless.live.channels import GROUP_ROULETTE_CALL, GROUP_USER
from venueless.live.decorators import command, event, room_action
from venueless.live.exceptions import ConsumerException
from venueless.live.modules.base import BaseModule


class RouletteModule(BaseModule):
    prefix = "roulette"

    # TODO: calls currently to not survive a reconnect or server restart
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.used = False
        self.calls = []

    @command("start")
    @room_action(
        permission_required=Permission.ROOM_ROULETTE_JOIN,
        module_required="networking.roulette",
    )
    async def start(self, body):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("roulette.start.missing_profile")

        self.used = True
        request, room_id = await roulette_request(
            self.consumer.user, self.room, self.consumer.socket_id
        )
        if room_id:
            await self.consumer.send_success(
                {
                    "status": "match",
                    "other_user": request.user.serialize_public(
                        trait_badges_map=self.consumer.world.config.get(
                            "trait_badges_map"
                        )
                    ),
                    "call_id": str(room_id),
                }
            )
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=request.user.id),
                {
                    "type": "roulette.match_found",
                    "socket_id": str(request.socket_id),
                    "data": {
                        "call_id": str(room_id),
                        "other_user": self.consumer.user.serialize_public(
                            trait_badges_map=self.consumer.world.config.get(
                                "trait_badges_map"
                            )
                        ),
                    },
                },
            )
            self.calls.append(str(room_id))
            await self.consumer.channel_layer.group_add(
                GROUP_ROULETTE_CALL.format(id=str(room_id)),
                self.consumer.channel_name,
            )
        else:
            await self.consumer.send_success({"status": "wait"})

    @command("stop")
    @room_action(
        permission_required=Permission.ROOM_ROULETTE_JOIN,
        module_required="networking.roulette",
    )
    async def stop(self, body):
        await roulette_cleanup(self.consumer.socket_id)
        await self.consumer.send_success({})

    @command("hangup")
    async def hangup(self, body):
        call_id = body.get("call")
        if not await is_member_of_roulette_call(call_id, self.consumer.user):
            raise ConsumerException("roulette.denied")
        await self.consumer.channel_layer.group_discard(
            GROUP_ROULETTE_CALL.format(id=call_id),
            self.consumer.channel_name,
        )
        await self.consumer.channel_layer.group_send(
            GROUP_ROULETTE_CALL.format(id=call_id),
            {"type": "roulette.hangup"},
        )
        try:
            self.calls.remove(call_id)
        except ValueError:
            pass
        await self.consumer.send_success({})

    @event("match_found")
    async def publish_match_found(self, body):
        if body.get("socket_id") == self.consumer.socket_id:
            call_id = body.get("data", {}).get("call_id")
            await self.consumer.send_json(["roulette.match_found", body.get("data")])
            self.calls.append(call_id)
            await self.consumer.channel_layer.group_add(
                GROUP_ROULETTE_CALL.format(id=call_id),
                self.consumer.channel_name,
            )

    @event("hangup")
    async def publish_hangup(self, body):
        await self.consumer.send_json(["roulette.hangup", {}])

    async def dispatch_disconnect(self, close_code):
        if self.used:
            await roulette_cleanup(self.consumer.socket_id)
        for call_id in self.calls:
            await self.consumer.channel_layer.group_discard(
                GROUP_ROULETTE_CALL.format(id=call_id),
                self.consumer.channel_name,
            )
