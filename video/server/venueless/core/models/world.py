import copy
from contextlib import suppress

import jwt
from django.contrib.postgres.fields import JSONField
from django.db import models


def default_permissions():
    return {
        "world.update": ["admin"],
        "world.secrets": ["admin", "api"],
        "world.announce": ["admin"],
        # API is an additional permissions since it might always give read-access to secret stuff, e.g. in world or room
        # configuration parameters
        "world.api": ["admin", "api"],
        "room.create": ["admin"],
        "room.announce": ["admin"],
        "room.update": ["admin"],
        "room.delete": ["admin"],
        "chat.moderate": ["admin"],
    }


class World(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=300)
    about = models.TextField(null=True, blank=True)
    config = JSONField(null=True, blank=True)
    permission_config = JSONField(null=True, blank=True, default=default_permissions)
    domain = models.CharField(max_length=250, unique=True, null=True, blank=True)

    def decode_token(self, token):
        for jwt_config in self.config["JWT_secrets"]:
            secret = jwt_config["secret"]
            audience = jwt_config["audience"]
            issuer = jwt_config["issuer"]
            with suppress(jwt.exceptions.InvalidSignatureError):
                return jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=audience,
                    issuer=issuer,
                )

    def has_permission(self, permission, traits, extra_config=None):
        permission_config = copy.deepcopy(self.permission_config)
        if extra_config:
            permission_config.update(extra_config)
        return permission in permission_config and all(
            trait in traits for trait in permission_config[permission]
        )
