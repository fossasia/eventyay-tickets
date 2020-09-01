import logging

from channels.db import database_sync_to_async

from venueless.core.permissions import Permission
from venueless.core.services.world import (
    _config_serializer,
    generate_tokens,
    get_world_config_for_user,
    notify_world_change,
    save_world,
)
from venueless.live.decorators import command, event, require_world_permission
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class WorldModule(BaseModule):
    prefix = "world"

    @event("update", refresh_world=True, refresh_user=True)
    async def push_world_update(self, body):
        world_config = await database_sync_to_async(get_world_config_for_user)(
            self.consumer.world,
            self.consumer.user,
        )
        await self.consumer.send_json(["world.updated", world_config])

    @command("config.get")
    @require_world_permission(Permission.WORLD_UPDATE)
    async def config_get(self, body):
        await self.consumer.send_success(_config_serializer(self.consumer.world).data)

    @command("config.patch")
    @require_world_permission(Permission.WORLD_UPDATE)
    async def config_patch(self, body):
        old = _config_serializer(self.consumer.world).data
        s = _config_serializer(self.consumer.world, data=body, partial=True)
        if s.is_valid():
            config_fields = (
                "theme",
                "dateLocale",
                "connection_limit",
                "bbb_defaults",
                "pretalx",
                "videoPlayer",
            )
            model_fields = ("title", "locale", "timezone", "roles", "trait_grants")
            update_fields = set()

            for f in model_fields:
                if f in body:
                    setattr(self.consumer.world, f, s.validated_data[f])
                    update_fields.add(f)

            for f in config_fields:
                if f in body:
                    if f == "pretalx" and not s.validated_data[f].get("domain"):
                        s.validated_data[f] = {}
                    self.consumer.world.config[f] = s.validated_data[f]
                    update_fields.add("config")

            await database_sync_to_async(self.consumer.world.save)(
                update_fields=list(update_fields)
            )
            new = await save_world(
                self.consumer.world,
                list(update_fields),
                by_user=self.consumer.user,
                old_data=old,
            )
            await self.consumer.send_success(new)
            await notify_world_change(self.consumer.world.id)
        else:
            await self.consumer.send_error(code="config.invalid")

    @command("tokens.generate")
    @require_world_permission(Permission.WORLD_UPDATE)  # TODO: stricter permission?
    async def tokens_generate(self, body):
        result = await generate_tokens(
            self.consumer.world,
            body["number"],
            body["traits"],
            body["days"],
            by_user=self.consumer.user,
        )
        await self.consumer.send_success({"results": result})
