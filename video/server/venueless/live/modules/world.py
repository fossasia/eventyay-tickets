import datetime
import logging
import uuid

import jwt
from channels.db import database_sync_to_async
from pytz import common_timezones
from rest_framework import serializers

from venueless.core.permissions import Permission
from venueless.core.services.world import get_world_config_for_user, notify_world_change
from venueless.live.decorators import command, event, require_world_permission
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class WorldConfigSerializer(serializers.Serializer):
    theme = serializers.DictField()
    roles = serializers.DictField()
    trait_grants = serializers.DictField()
    bbb_defaults = serializers.DictField()
    pretalx = serializers.DictField()
    title = serializers.CharField()
    locale = serializers.CharField()
    dateLocale = serializers.CharField()
    timezone = serializers.ChoiceField(choices=[(a, a) for a in common_timezones])
    connection_limit = serializers.IntegerField(allow_null=True)
    available_permissions = serializers.SerializerMethodField("_available_permissions")

    def _available_permissions(self, *args):
        return [d.value for d in Permission]


class WorldModule(BaseModule):
    prefix = "world"

    @event("update", refresh_world=True, refresh_user=True)
    async def push_world_update(self, body):
        world_config = await database_sync_to_async(get_world_config_for_user)(
            self.consumer.world, self.consumer.user,
        )
        await self.consumer.send_json(["world.updated", world_config])

    def _config_serializer(self, *args, **kwargs):
        bbb_defaults = self.consumer.world.config.get("bbb_defaults", {})
        bbb_defaults.pop("secret", None)  # Protect secret legacy contents
        return WorldConfigSerializer(
            instance={
                "theme": self.consumer.world.config.get("theme", {}),
                "title": self.consumer.world.title,
                "locale": self.consumer.world.locale,
                "dateLocale": self.consumer.world.config.get("dateLocale", "en-ie"),
                "roles": self.consumer.world.roles,
                "bbb_defaults": bbb_defaults,
                "pretalx": self.consumer.world.config.get("pretalx", {}),
                "timezone": self.consumer.world.timezone,
                "trait_grants": self.consumer.world.trait_grants,
                "connection_limit": self.consumer.world.config.get(
                    "connection_limit", 0
                ),
            },
            *args,
            **kwargs
        )

    @command("config.get")
    @require_world_permission(Permission.WORLD_UPDATE)
    async def config_get(self, body):
        await self.consumer.send_success(self._config_serializer().data)

    @command("config.patch")
    @require_world_permission(Permission.WORLD_UPDATE)
    async def config_patch(self, body):
        s = self._config_serializer(data=body, partial=True)
        if s.is_valid():
            config_fields = ("theme", "dateLocale", "connection_limit", "bbb_defaults", "pretalx")
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
            await self.consumer.send_success(self._config_serializer().data)
            await notify_world_change(self.consumer.world.id)
        else:
            await self.consumer.send_error(code="config.invalid")

    @command("tokens.generate")
    @require_world_permission(Permission.WORLD_UPDATE)  # TODO: stricter permission?
    async def tokens_generate(self, body):
        jwt_config = self.consumer.world.config["JWT_secrets"][0]
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]
        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=body["days"])
        result = []
        for i in range(body["number"]):
            payload = {
                "iss": issuer,
                "aud": audience,
                "exp": exp,
                "iat": iat,
                "uid": str(uuid.uuid4()),
                "traits": body["traits"],
            }
            token = jwt.encode(payload, secret, algorithm="HS256").decode("utf-8")
            result.append(token)
        await self.consumer.send_success({"results": result})
