import logging

from channels.db import database_sync_to_async

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
        self.service = ExhibitionService(self.consumer.world)

    async def dispatch_disconnect(self, close_code):
        if self.consumer.user:
            for request in await self.service.get_open_requests_from_user(
                user=self.consumer.user
            ):
                await self.contact_cancel({"contact_request": request["id"]})

    @command("list.all")
    async def list_all(self, body):
        if not await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.WORLD_ROOMS_CREATE_EXHIBITION
        ):
            exhibitors = await self.service.get_all_exhibitors(
                staff_includes_user=self.consumer.user
            )
        else:
            exhibitors = await self.service.get_all_exhibitors()
        await self.consumer.send_success({"exhibitors": exhibitors})

    @command("delete")
    @require_world_permission(Permission.WORLD_ROOMS_CREATE_EXHIBITION)
    async def delete(self, body):
        staff = await self.service.get_staff(exhibitor_id=body["exhibitor"])
        if not await self.service.delete(
            exhibitor_id=body["exhibitor"], by_user=self.consumer.user
        ):
            await self.consumer.send_error("exhibition.unknown_exhibitor")
        else:
            for user_id in staff:
                data = await database_sync_to_async(
                    self.service.get_exhibition_data_for_user
                )(user_id)
                await self.consumer.channel_layer.group_send(
                    GROUP_USER.format(id=str(user_id)),
                    {"type": "exhibition.exhibition_data_update", "data": data},
                )
            await self.consumer.send_success({})

    @command("patch")
    async def patch(self, body):
        staff = []
        if body["id"] != "":
            staff += await self.service.get_staff(exhibitor_id=body["id"])

        if await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.WORLD_ROOMS_CREATE_EXHIBITION
        ):
            exclude_fields = set()
        elif self.consumer.user.id in staff:
            exclude_fields = {"staff", "size", "name", "sorting_priority", "room_id"}
        else:
            await self.consumer.send_error("exhibition.not_staff_member")
            return

        exhibitor = await self.service.patch(
            exhibitor=body,
            world=self.consumer.world,
            by_user=self.consumer.user,
            exclude_fields=exclude_fields,
        )

        for user in exhibitor["staff"]:
            if user["id"] not in staff:
                staff.append(user["id"])

        for user_id in staff:
            data = await database_sync_to_async(
                self.service.get_exhibition_data_for_user
            )(user_id)
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=str(user_id)),
                {"type": "exhibition.exhibition_data_update", "data": data},
            )

        if not exhibitor:
            await self.consumer.send_error("exhibition.unknown_exhibitor")
        else:
            await self.consumer.send_success({"exhibitor": exhibitor})

    @command("list")
    @room_action(module_required="exhibition.native")
    async def list(self, body):
        exhibitors = await self.service.get_exhibitors(room_id=body["room"])
        await self.consumer.send_success({"exhibitors": exhibitors})

    @command("get")
    async def get(self, body):
        exhibitor = await self.service.get_exhibitor(
            exhibitor_id=body["exhibitor"], track_view_for_user=self.consumer.user
        )
        if not exhibitor:
            await self.consumer.send_error("exhibition.unknown_exhibitor")
            return
        await self.consumer.send_success({"exhibitor": exhibitor})

    @command("get.staffed_by_user")
    async def staffed_by_user(self, body):
        exhibitors = await self.service.get_exhibitions_staffed_by_user(
            user_id=body["user_id"]
        )
        await self.consumer.send_success({"exhibitors": exhibitors})

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
                {
                    "type": "exhibition.contact_request",
                    "contact_request": request,
                },
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
                {
                    "type": "exhibition.contact_close",
                    "contact_request": request,
                },
            )

    @command("contact_accept")
    async def contact_accept(self, body):
        channel = body["channel"]
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
            {
                "type": "exhibition.contact_accepted",
                "contact_request": request,
                "channel": channel,
            },
        )
        for user_id in staff:
            await self.consumer.channel_layer.group_send(
                GROUP_USER.format(id=str(user_id)),
                {"type": "exhibition.contact_close", "contact_request": request},
            )

    @command("add_staff")
    @require_world_permission(Permission.WORLD_ROOMS_CREATE_EXHIBITION)
    async def add_staff(self, body):
        staff = await self.service.add_staff(
            exhibitor_id=body["exhibitor"],
            user_id=body["user"],
            by_user=self.consumer.user,
        )
        if not staff:
            await self.consumer.send_error("exhibition.unknown_user_or_exhibitor")
            return
        await self.consumer.send_success()

    @command("remove_staff")
    @require_world_permission(Permission.WORLD_ROOMS_CREATE_EXHIBITION)
    async def remove_staff(self, body):
        if not await self.service.remove_staff(
            exhibitor_id=body["exhibitor"],
            user_id=body["user"],
            by_user=self.consumer.user,
        ):
            await self.consumer.send_error("exhibition.unknown_user_or_exhibitor")
            return
        await self.consumer.send_success()

    @event("contact_request")
    async def contact_request(self, body):
        await self.consumer.send_json(
            [
                "exhibition.contact_request",
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("contact_accepted")
    async def contact_accepted(self, body):
        await self.consumer.send_json(
            [
                "exhibition.contact_accepted",
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("contact_close")
    async def contact_request_cancel(self, body):
        await self.consumer.send_json(
            [
                "exhibition.contact_request_close",
                {k: v for k, v in body.items() if k != "type"},
            ]
        )

    @event("exhibition_data_update")
    async def exhibition_data_update(self, body):
        await self.consumer.send_json(
            [
                "exhibition.exhibition_data_update",
                {k: v for k, v in body.items() if k != "type"},
            ]
        )
