import logging

from venueless.core.permissions import Permission
from venueless.core.services.poster import PosterService
from venueless.live.decorators import command, require_world_permission, room_action
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class PosterModule(BaseModule):
    prefix = "poster"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = PosterService(self.consumer.world)

    @command("list.all")
    async def list_all(self, body):
        if not await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.WORLD_ROOMS_CREATE_POSTER
        ):
            posters = await self.service.get_all_posters(
                presenter_includes_user=self.consumer.user, list_format=True
            )
        else:
            posters = await self.service.get_all_posters()
        await self.consumer.send_success(posters)

    @command("delete")
    @require_world_permission(Permission.WORLD_ROOMS_CREATE_POSTER)
    async def delete(self, body):
        if not await self.service.delete(
            poster_id=body["poster"], by_user=self.consumer.user
        ):
            await self.consumer.send_error("poster.unknown_poster")
        await self.consumer.send_success({})

    @command("patch")
    async def patch(self, body):
        presenters = []
        if body["id"] != "":
            presenters = await self.service.get_presenters(poster_id=body["id"])

        if await self.consumer.world.has_permission_async(
            user=self.consumer.user, permission=Permission.WORLD_ROOMS_CREATE_POSTER
        ):
            exclude_fields = set()
        elif self.consumer.user.id in presenters:
            exclude_fields = {
                "presenters",
                "parent_room",
                "channel",
                "presentation_room",
                "tags",
                "category",
                "schedule_session",
            }
        else:
            await self.consumer.send_error("poster.not_presenter")
            return

        poster = await self.service.patch(
            data=body,
            world=self.consumer.world,
            by_user=self.consumer.user,
            exclude_fields=exclude_fields,
        )

        if not poster:
            await self.consumer.send_error("poster.unknown_poster")
        else:
            await self.consumer.send_success(poster)

    @command("list")
    @room_action(module_required="poster.native")
    async def list(self, body):
        posters = await self.service.get_posters(
            room_id=body["room"],
            user=self.consumer.user,
            list_format=True,
        )
        await self.consumer.send_success(posters)

    @command("get")
    async def get(self, body):
        poster = await self.service.get_poster(body["poster"], self.consumer.user)
        if not poster:
            await self.consumer.send_error("poster.unknown_poster")
            return
        await self.consumer.send_success(poster)

    @command("get.presented_by_user")
    async def presented_by_user(self, body):
        posters = await self.service.get_posters_presented_by_user(
            user_id=body["user_id"]
        )
        await self.consumer.send_success(posters)

    @command("vote")
    async def vote(self, body):
        poster = await self.service.get_poster(poster_id=body["poster"])
        if not poster:
            await self.consumer.send_error("poster.unknown_poster")
            return
        vote = await self.service.vote(poster_id=poster["id"], user=self.consumer.user)
        await self.consumer.send_success(vote)

    @command("unvote")
    async def unvote(self, body):
        poster = await self.service.get_poster(poster_id=body["poster"])
        if not poster:
            await self.consumer.send_error("poster.unknown_poster")
            return
        await self.service.unvote(poster_id=poster["id"], user=self.consumer.user)
        await self.consumer.send_success()
