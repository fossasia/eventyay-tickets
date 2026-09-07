from collections import defaultdict
from urllib.parse import urljoin

import icalendar
import jwt
from django.conf import settings
from django.core.files import File
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import JSONField
from django.utils.crypto import get_random_string

from eventyay.base.models.auth import User
from eventyay.base.models.cache import VersionedModel
from eventyay.core.permissions import (
    MAX_PERMISSIONS_IF_SILENCED,
    ORGANIZER_ROLES,
    SYSTEM_ROLES,
    Permission,
    default_grants,
    default_roles,
    normalize_permission_value,
    traits_match_required,
)
from eventyay.core.utils.json import CustomJSONEncoder
from eventyay.base.models.chat import ChatEvent, Membership
from eventyay.base.models.feedback import Feedback
from eventyay.base.models.poll import Poll
from eventyay.base.models.room import Reaction, RoomView
from eventyay.base.models.storage_model import StoredFile


FEATURE_FLAGS = [
    "schedule-control",
    "roulette",
    "muxdata",
    "page.landing",
    "zoom",
    "janus",
    "polls",
    "conftool",
    "cross-origin-isolation",
]


def default_feature_flags():
    return ["chat-moderation"]


class World(VersionedModel):
    id = models.CharField(
        primary_key=True,
        max_length=50,
        validators=[RegexValidator(regex=r"^[a-z0-9]+$")],
    )
    title = models.CharField(max_length=300)
    config = JSONField(null=True, blank=True)
    roles = JSONField(
        null=True, blank=True, default=default_roles, encoder=CustomJSONEncoder
    )
    trait_grants = JSONField(null=True, blank=True, default=default_grants)
    domain = models.CharField(
        max_length=250,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r"^[a-z0-9-.:]+(/[a-zA-Z0-9-_./]*)?$")],
    )
    locale = models.CharField(
        max_length=100,
        default="en",
        choices=(
            ("en", "English"),
            ("de", "German"),
        ),
    )
    timezone = models.CharField(max_length=120, default="Europe/Berlin")
    feature_flags = JSONField(blank=True, default=default_feature_flags)
    external_auth_url = models.URLField(null=True, blank=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return f"{self.id} ({self.title})"

    def decode_token(self, token, allow_raise=False):
        exc = None
        for jwt_config in self.config["JWT_secrets"]:
            secret = jwt_config["secret"]
            audience = jwt_config["audience"]
            issuer = jwt_config["issuer"]
            try:
                return jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=audience,
                    issuer=issuer,
                )
            except jwt.exceptions.ExpiredSignatureError:
                if allow_raise:
                    raise
            except jwt.exceptions.InvalidTokenError as e:
                exc = e
        if exc and allow_raise:
            raise exc

    def has_permission_implicit(
        self,
        *,
        traits,
        permissions: list[Permission],
        room=None,
        allow_empty_traits=True,
    ):
        for role, required_traits in self.trait_grants.items():
            if role in ORGANIZER_ROLES:
                if not required_traits or not traits_match_required(traits, required_traits):
                    continue
            else:
                if not (traits_match_required(traits, required_traits) and (required_traits or allow_empty_traits)):
                    continue
            role_perms = self.roles.get(role, SYSTEM_ROLES.get(role, []))
            if any(
                normalize_permission_value(p) in role_perms
                for p in permissions
            ):
                return True

        if room:
            for role, required_traits in room.trait_grants.items():
                if role in ORGANIZER_ROLES:
                    if not required_traits or not traits_match_required(traits, required_traits):
                        continue
                else:
                    if not (traits_match_required(traits, required_traits) and (required_traits or allow_empty_traits)):
                        continue
                role_perms = self.roles.get(role, SYSTEM_ROLES.get(role, []))
                if any(
                    normalize_permission_value(p) in role_perms
                    for p in permissions
                ):
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
            traits=user.traits or [],
            permissions=permission,
            room=room,
            allow_empty_traits=user.type == User.UserType.PERSON,
        ):
            return True

        roles = user.get_role_grants(room)
        for r in roles:
            role_perms = self.roles.get(r, SYSTEM_ROLES.get(r, []))
            if any(normalize_permission_value(p) in role_perms for p in permission):
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
            traits=user.traits or [],
            permissions=permission,
            room=room,
            allow_empty_traits=user.type == User.UserType.PERSON,
        ):
            return True

        roles = await user.get_role_grants_async(room)
        for r in roles:
            role_perms = self.roles.get(r, SYSTEM_ROLES.get(r, []))
            if any(normalize_permission_value(p) in role_perms for p in permission):
                return True

    def get_all_permissions(self, user):
        result = defaultdict(set)
        if user.is_banned:  # pragma: no cover
            # safeguard only
            return result

        allow_empty_traits = user.type == User.UserType.PERSON
        user_traits = user.traits or []

        for role, required_traits in self.trait_grants.items():
            if role in ORGANIZER_ROLES:
                if not required_traits or not traits_match_required(user_traits, required_traits):
                    continue
            else:
                if not (traits_match_required(user_traits, required_traits) and (required_traits or allow_empty_traits)):
                    continue
            result[self].update(self.roles.get(role, SYSTEM_ROLES.get(role, [])))

        for grant in user.world_grants.all():
            result[self].update(
                self.roles.get(grant.role, SYSTEM_ROLES.get(grant.role, []))
            )

        for room in self.rooms.all():
            for role, required_traits in room.trait_grants.items():
                if role in ORGANIZER_ROLES:
                    if not required_traits or not traits_match_required(user_traits, required_traits):
                        continue
                else:
                    if not (traits_match_required(user_traits, required_traits) and (required_traits or allow_empty_traits)):
                        continue
                result[room].update(
                    self.roles.get(role, SYSTEM_ROLES.get(role, []))
                )

        for grant in user.room_grants.select_related("room"):
            result[grant.room].update(
                self.roles.get(grant.role, SYSTEM_ROLES.get(grant.role, []))
            )
        if user.is_silenced:
            for key in result.keys():
                result[key] &= MAX_PERMISSIONS_IF_SILENCED

        return result

    def clear_data(self):
        """
        Clears all personal information. It generally leaves structure such as rooms intact, but to make
        sure all personal data is scrubbed, it also clears all uploaded files.
        """

        self.audit_logs.all().delete()
        self.world_grants.all().delete()
        self.room_grants.all().delete()
        self.bbb_calls.all().delete()
        ChatEvent.objects.filter(channel__world=self).delete()
        Membership.objects.filter(channel__world=self).delete()
        Reaction.objects.filter(room__world=self).delete()
        RoomView.objects.filter(room__world=self).delete()
        WorldView.objects.filter(world=self).delete()
        Question.objects.filter(room__world=self).delete()
        Poll.objects.filter(room__world=self).delete()
        Feedback.objects.filter(world=self).delete()

        for f in StoredFile.objects.filter(world=self):
            f.full_delete()

        self.user_set.all().delete()
        self.domain = None
        self.save()

    def clone_from(self, old, new_secrets):
        from eventyay.base.models import Channel
        from eventyay.base.models.storage_model import StoredFile

        if self.pk == old.pk:
            raise ValueError("Illegal attempt to clone into same world")

        def clone_stored_files(*, inst=None, attrs=None, struct=None, url=None):
            if inst and attrs:
                for a in attrs:
                    if getattr(inst, a):
                        setattr(inst, a, clone_stored_files(url=getattr(inst, a)))
            elif url:
                media_base = urljoin(
                    f'http{"" if settings.DEBUG else "s"}://{old.domain}',
                    settings.MEDIA_URL,
                )
                if url.startswith(media_base):
                    mlen = len(media_base)
                    fname = url[mlen:]
                    try:
                        src = StoredFile.objects.get(world=old, file=fname)
                    except StoredFile.DoesNotExist:
                        return url
                    sf = StoredFile.objects.create(
                        world=self,
                        date=src.date,
                        filename=src.filename,
                        type=src.type,
                        file=File(src.file, src.filename),
                        public=src.public,
                        user=None,
                    )
                    return sf.file.url
                else:
                    # probably external or something we don't understand
                    return url
            elif isinstance(struct, str):
                return clone_stored_files(url=struct)
            elif isinstance(struct, dict):
                return {k: clone_stored_files(struct=v) for k, v in struct.items()}
            elif isinstance(struct, (list, tuple)):
                return [clone_stored_files(struct=e) for e in struct]
            else:
                return struct

        self.config = old.config
        if new_secrets:
            secret = get_random_string(length=64)
            self.config["JWT_secrets"] = [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": secret,
                }
            ]
        self.roles = old.roles
        self.trait_grants = old.trait_grants
        self.locale = old.locale
        self.timezone = old.timezone
        self.feature_flags = old.feature_flags
        self.external_auth_url = old.external_auth_url
        self.save()

        for r in old.rooms.all():
            try:
                has_channel = r.channel
            except Exception:
                has_channel = False

            r.pk = None
            r.world = self
            r.module_config = clone_stored_files(struct=r.module_config)
            r.save()
            if has_channel:
                Channel.objects.create(room=r, world=self)


class PlannedUsage(models.Model):
    world = models.ForeignKey(
        World, on_delete=models.CASCADE, related_name="planned_usages"
    )
    start = models.DateField()
    end = models.DateField()
    attendees = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("start",)

    def as_ical(self):
        event = icalendar.Event()
        event["uid"] = f"{self.world.id}-{self.id}"
        event["dtstart"] = self.start
        event["dtend"] = self.start
        event["summary"] = self.world.title
        event["description"] = self.notes
        event["url"] = self.world.domain
        return event


class WorldView(models.Model):
    world = models.ForeignKey(
        to="World", related_name="views", on_delete=models.CASCADE
    )
    start = models.DateTimeField(
        auto_now_add=True,
    )
    end = models.DateTimeField(
        null=True, db_index=True
    )  # index required for control/ dashboard
    user = models.ForeignKey(
        to="user", related_name="world_views", on_delete=models.CASCADE
    )

    class Meta:
        indexes = [
            models.Index(fields=["start"]),
        ]
