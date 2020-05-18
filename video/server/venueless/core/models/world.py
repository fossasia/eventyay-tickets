from collections import defaultdict
from contextlib import suppress

import jwt
from channels.db import database_sync_to_async
from django.contrib.postgres.fields import JSONField
from django.db import models

from venueless.core.permissions import Permission
from venueless.core.utils.json import CustomJSONEncoder


def default_roles():
    attendee = [Permission.WORLD_VIEW]
    viewer = attendee + [Permission.ROOM_VIEW, Permission.ROOM_CHAT_READ]
    participant = viewer + [
        Permission.ROOM_CHAT_JOIN,
        Permission.ROOM_CHAT_SEND,
        Permission.ROOM_BBB_JOIN,
    ]
    room_creator = [Permission.WORLD_ROOMS_CREATE]
    room_owner = participant + [
        Permission.ROOM_UPDATE,
        Permission.ROOM_INVITE,
        Permission.ROOM_DELETE,
    ]
    speaker = participant + [Permission.ROOM_BBB_MODERATE]
    moderator = speaker + [
        Permission.ROOM_CHAT_MODERATE,
        Permission.ROOM_ANNOUNCE,
        Permission.WORLD_ANNOUNCE,
    ]
    admin = (
        moderator
        + room_creator
        + [Permission.WORLD_UPDATE, Permission.ROOM_DELETE, Permission.ROOM_UPDATE,]
    )
    apiuser = admin + [Permission.WORLD_API, Permission.WORLD_SECRETS]
    return {
        "attendee": attendee,
        "viewer": viewer,
        "participant": participant,
        "room_creator": room_creator,
        "room_owner": room_owner,
        "speaker": speaker,
        "moderator": moderator,
        "admin": admin,
        "apiuser": apiuser,
    }


def default_grants():
    return {
        "viewer": [],
    }


class World(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=300)
    about = models.TextField(null=True, blank=True)
    config = JSONField(null=True, blank=True)
    roles = JSONField(
        null=True, blank=True, default=default_roles, encoder=CustomJSONEncoder
    )
    trait_grants = JSONField(null=True, blank=True, default=default_grants)
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

    def has_permission_implicit(self, *, traits, permission: Permission, room=None):
        for role, required_traits in self.trait_grants.items():
            if isinstance(required_traits, list) and all(
                r in traits for r in required_traits
            ):
                if permission.value in self.roles.get(role, []):
                    return True

        if room:
            for role, required_traits in room.trait_grants.items():
                if isinstance(required_traits, list) and all(
                    r in traits for r in required_traits
                ):
                    if permission.value in self.roles.get(role, []):
                        return True

    def has_permission(self, *, user, permission: Permission, room=None):
        """
        Returns whether a user holds a given permission either on the world or on a specific room.
        """
        if self.has_permission_implicit(
            traits=user.traits, permission=permission, room=room
        ):
            return True

        roles = user.get_role_grants(room)
        for r in roles:
            if permission.value in self.roles.get(r, []):
                return True

    async def has_permission_async(self, *, user, permission: Permission, room=None):
        """
        Returns whether a user holds a given permission either on the world or on a specific room.
        """
        if self.has_permission_implicit(
            traits=user.traits, permission=permission, room=room
        ):
            return True

        roles = await database_sync_to_async(user.get_role_grants)(room)
        for r in roles:
            if permission.value in self.roles.get(r, []):
                return True

    def get_all_permissions(self, user):
        result = defaultdict(set)
        for role, required_traits in self.trait_grants.items():
            if isinstance(required_traits, list) and all(
                r in user.traits for r in required_traits
            ):
                result[self].update(self.roles.get(role, []))

        for grant in user.world_grants.all():
            result[self].update(self.roles.get(grant.role, []))

        for room in self.rooms.all():
            for role, required_traits in room.trait_grants.items():
                if isinstance(required_traits, list) and all(
                    r in user.traits for r in required_traits
                ):
                    result[room].update(self.roles.get(role, []))

        for grant in user.room_grants.select_related("room"):
            result[grant.room].update(self.roles.get(grant.role, []))
        return result
