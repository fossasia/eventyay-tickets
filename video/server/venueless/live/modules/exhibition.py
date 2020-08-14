import logging

from venueless.core.permissions import Permission
from venueless.core.services.exhibition import ExhibitionService
from venueless.live.channels import GROUP_USER
from venueless.live.decorators import (
    command,
    event,
    require_world_permission,
    room_action,
)
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class ExhibitionModule(BaseModule):
    prefix = "exhibition"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = ExhibitionService(self.consumer.world.id)

    async def dispatch_disconnect(self, close_code):
        if self.consumer.user:
            for request in await self.service.get_requests_from_user(
                user=self.consumer.user
            ):
                await self.contact_cancel({"contact_request": request["id"]})

    @command("list")
    @room_action(module_required="exhibition.native")
    async def list(self, body):
        exhibitors = await self.service.get_exhibitors(room_id=body["room"])
        await self.consumer.send_success({"exhibitors": exhibitors})

    @command("get")
    async def get(self, body):
        exhibitor = await self.service.get_exhibitor(exhibitor_id=body["exhibitor"])
        if not exhibitor:
            await self.consumer.send_error("exhibition.unknown_exhibitor")
            return
        await self.consumer.send_success({"exhibitor": exhibitor})

    @command("contact")
    @require_world_permission(Permission.WORLD_EXHIBITION_CONTACT)
    async def contact(self, body):
        exhibitor = await self.service.get_exhibitor(exhibitor_id=body["exhibitor"])
        if not exhibitor:
            await self.consumer.send_error("exhibition.unknown_exhibitor")
            return
        request = await self.service.contact(
            exhibitor_id=exhibitor["id"], user=self.consumer.user
        )
        await self.consumer.send_success({"contact_request": request})
        for staff_member in exhibitor["staff"]:
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=str(staff_member["id"])),
                {"type": "exhibition.contact_request", "contact_request": request,},
            )

    @command("contact_cancel")
    @require_world_permission(Permission.WORLD_EXHIBITION_CONTACT)
    async def contact_cancel(self, body):
        request = await self.service.missed(contact_request_id=body["contact_request"])
        if not request:
            await self.consumer.send_error("exhibition.unknown_contact_request")
            return
        await self.consumer.send_success()
        staff = await self.service.get_staff(exhibitor_id=request["exhibitor"]["id"])
        for user_id in staff:
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=str(user_id)),
                {"type": "exhibition.contact_close", "contact_request": request,},
            )

    @command("contact_accept")
    async def contact_accept(self, body):
        request = await self.service.accept(
            contact_request_id=body["contact_request"], staff=self.consumer.user
        )
        if not request:
            await self.consumer.send_error("exhibition.unknown_contact_request")
            return
        staff = await self.service.get_staff(exhibitor_id=request["exhibitor"]["id"])
        if self.consumer.user.id not in staff:
            await self.consumer.send_error("exhibition.not_staff_member")
            return
        await self.consumer.send_success()
        await self.consumer.channel_layer.group_send(
            GROUP_USER.format(id=request["user"]["id"]),
            {"type": "exhibition.contact_accepted", "contact_request": request,},
        )
        for user_id in staff:
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=str(user_id)),
                {"type": "exhibition.contact_close", "contact_request": request,},
            )

    @command("add_staff")
    @require_world_permission(Permission.WORLD_ROOMS_CREATE_EXHIBITION)
    async def add_staff(self, body):
        staff = await self.service.add_staff(
            exhibitor_id=body["exhibitor"], user_id=body["user"]
        )
        if not staff:
            await self.consumer.send_error("exhibition.unknown_user_or_exhibitor")
            return
        await self.consumer.send_success()

    @command("remove_staff")
    @require_world_permission(Permission.WORLD_ROOMS_CREATE_EXHIBITION)
    async def remove_staff(self, body):
        if not await self.service.remove_staff(
            exhibitor_id=body["exhibitor"], user_id=body["user"]
        ):
            await self.consumer.send_error("exhibition.unknown_user_or_exhibitor")
            return
        await self.consumer.send_success()

    @event("contact_request")
    async def contact_request(self, body):
        await self.consumer.send_json(
            ["exhibition.contact_request", body["contact_request"]]
        )

    @event("contact_accepted")
    async def contact_accepted(self, body):
        await self.consumer.send_json(
            ["exhibition.contact_accepted", body["contact_request"]]
        )

    @event("contact_close")
    async def contact_request_cancel(self, body):
        await self.consumer.send_json(
            ["exhibition.contact_request_close", body["contact_request"]]
        )
