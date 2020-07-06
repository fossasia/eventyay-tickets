from collections import defaultdict
from contextlib import suppress
from typing import List

import jwt
from django.contrib.postgres.fields import JSONField
from django.db import models

from venueless.core.models.cache import VersionedModel
from venueless.core.permissions import MAX_PERMISSIONS_IF_SILENCED, Permission
from venueless.core.utils.json import CustomJSONEncoder


def default_roles():
    attendee = [Permission.WORLD_VIEW]
    viewer = attendee + [Permission.ROOM_VIEW, Permission.ROOM_CHAT_READ]
    participant = viewer + [
        Permission.ROOM_CHAT_JOIN,
        Permission.ROOM_CHAT_SEND,
        Permission.ROOM_BBB_JOIN,
    ]
    room_creator = [Permission.WORLD_ROOMS_CREATE_CHAT]
    room_owner = participant + [
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
        + [
            Permission.WORLD_UPDATE,
            Permission.ROOM_DELETE,
            Permission.ROOM_UPDATE,
            Permission.WORLD_ROOMS_CREATE_BBB,
            Permission.WORLD_ROOMS_CREATE_STAGE,
            Permission.WORLD_USERS_LIST,
            Permission.WORLD_USERS_MANAGE,
            Permission.WORLD_GRAPHS,
        ]
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


class World(VersionedModel):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=300)
    config = JSONField(null=True, blank=True)
    roles = JSONField(
        null=True, blank=True, default=default_roles, encoder=CustomJSONEncoder
    )
    trait_grants = JSONField(null=True, blank=True, default=default_grants)
    domain = models.CharField(max_length=250, unique=True, null=True, blank=True)
    locale = models.CharField(max_length=100, default="en")
    timezone = models.CharField(max_length=120, default="Europe/Berlin")

    def decode_token(self, token):
        for jwt_config in self.config["JWT_secrets"]:
            secret = jwt_config["secret"]
            audience = jwt_config["audience"]
            issuer = jwt_config["issuer"]
            with suppress(
                jwt.exceptions.InvalidSignatureError,
                jwt.exceptions.ExpiredSignatureError,
            ):
                return jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=audience,
                    issuer=issuer,
                )

    def has_permission_implicit(
        self, *, traits, permissions: List[Permission], room=None
    ):
        for role, required_traits in self.trait_grants.items():
            if isinstance(required_traits, list) and all(
                r in traits for r in required_traits
            ):
                if any(p.value in self.roles.get(role, []) for p in permissions):
                    return True

        if room:
            for role, required_traits in room.trait_grants.items():
                if isinstance(required_traits, list) and all(
                    r in traits for r in required_traits
                ):
                    if any(p.value in self.roles.get(role, []) for p in permissions):
                        return True

    def has_permission(self, *, user, permission: Permission, room=None):
        """
        Returns whether a user holds a given permission either on the world or on a specific room.
        ``permission`` can be one ``Permission`` or a list of these, in which case it will perform an OR lookup.
        """
        if user.is_banned:  # pragma: no cover
            # safeguard only
            return False

        if not isinstance(permission, list):
            permission = [permission]

        if user.is_silenced and not any(
            p in MAX_PERMISSIONS_IF_SILENCED for p in permission
        ):
            return False

        if self.has_permission_implicit(
            traits=user.traits, permissions=permission, room=room
        ):
            return True

        roles = user.get_role_grants(room)
        for r in roles:
            if any(p.value in self.roles.get(r, []) for p in permission):
                return True

    async def has_permission_async(self, *, user, permission: Permission, room=None):
        """
        Returns whether a user holds a given permission either on the world or on a specific room.
        ``permission`` can be one ``Permission`` or a list of these, in which case it will perform an OR lookup.
        """
        if user.is_banned:  # pragma: no cover
            # safeguard only
            return False

        if not isinstance(permission, list):
            permission = [permission]

        if user.is_silenced and not any(
            p in MAX_PERMISSIONS_IF_SILENCED for p in permission
        ):
            return False

        if self.has_permission_implicit(
            traits=user.traits, permissions=permission, room=room
        ):
            return True

        roles = await user.get_role_grants_async(room)
        for r in roles:
            if any(p.value in self.roles.get(r, []) for p in permission):
                return True

    def get_all_permissions(self, user):
        result = defaultdict(set)
        if user.is_banned:  # pragma: no cover
            # safeguard only
            return result

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
        if user.is_silenced:
            for k, v in result.items():
                result[k] &= MAX_PERMISSIONS_IF_SILENCED

        return result
