import uuid
from functools import cached_property

from django.db import models
from django.db.models import Exists, JSONField, OuterRef, Q
from django.db.models.expressions import RawSQL, Value
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from i18nfield.fields import I18nCharField

from eventyay.base.models.settings import GlobalSettings
from eventyay.base.models import OrderedModel, PretalxModel
from eventyay.base.models.auth import User
from eventyay.base.models.cache import VersionedModel
from eventyay.core.permissions import SYSTEM_ROLES, Permission
from eventyay.common.urls import EventUrls
from eventyay.talk_rules.agenda import is_agenda_visible
from eventyay.talk_rules.event import can_change_event_settings
from eventyay.talk_rules.submission import orga_can_change_submissions


def empty_module_config():
    return []


def default_grants():
    return {
        "viewer": [],
    }


class RoomQuerySet(models.QuerySet):
    def with_permission(
        self, *, user=None, traits=None, event, permission=Permission.ROOM_VIEW
    ):
        from .auth import RoomGrant, EventGrant

        traits = traits or user.traits
        allow_empty_traits = not user or user.type == User.UserType.PERSON
        if event.has_permission_implicit(
            traits=traits,
            permissions=[permission],
            allow_empty_traits=allow_empty_traits,
        ):
            # User has the permission globally, nothing to do
            return self.all()

        # Get all roles that grant view access
        roles = [
            role
            for role, permissions in [
                *event.roles.items(),
                *SYSTEM_ROLES.items(),
            ]
            if permission.value in permissions
        ]

        if not roles:  # pragma: no cover
            # No role grants access, impossible
            return self.none()

        if user:
            sq_user_has_room_grant = RoomGrant.objects.filter(
                user=user, event=event, room_id=OuterRef("pk"), role__in=roles
            )
            sq_user_has_event_grant = EventGrant.objects.filter(
                user=user, event=event, role__in=roles
            )
            qs = self.annotate(
                user_has_room_grant=Exists(sq_user_has_room_grant),
                user_has_event_grant=Exists(sq_user_has_event_grant),
            )
            requirements = Q(user_has_room_grant=True) | Q(user_has_event_grant=True)
        else:
            qs = self
            requirements = Q()

        # Implicit role grants, i.e. grants given by trait_grants values on the room itself
        # We calculate this entirely in SQL for performance reasons. This is a little more complicated
        # since trait_grants can contain AND and OR restrictions.
        # For example, if we know from above the "moderator" role would grant the required permission, we need to
        # check the trait_grants["moderator"] value of the room, which always is an array. All values inside the
        # array are connected as AND restrictions. However, the value may either be strings (user must have that trait)
        # or arrays (user must have one of the traits -- OR). We therefore need to do In-SQL type checks.
        # In case it is an empty array, everyone is permitted, unless allow_empty_traits is set to False.
        # When our user has traits, this is automatically ensured by the ALL() statement, but when traits=[] we
        # need to do a special case check since "IN ()" is not valid SQL
        for i, role in enumerate(roles):
            if traits:
                ext = ""
                ext_args = []
                if not allow_empty_traits:
                    ext = " AND jsonb_array_length(trait_grants->%s) > 0"
                    ext_args.append(role)

                qs = qs.annotate(
                    **{
                        f"has_role_{i}": RawSQL(
                            f"""(
                            trait_grants ? %s AND
                            trait_grants->%s IS NOT NULL AND
                            TRUE = ALL(
                                SELECT (
                                    CASE jsonb_typeof(d{i}.elem)
                                        WHEN 'array' THEN EXISTS(SELECT 1 FROM jsonb_array_elements(d{i}.elem) e{i}(elem) WHERE e{i}.elem#>>'{"{}"}' IN %s )
                                        ELSE d{i}.elem#>>'{"{}"}' IN %s
                                    END
                                ) FROM jsonb_array_elements( trait_grants->%s ) AS d{i}(elem)
                            ) {ext}
                        )""",
                            (
                                role,  # ? check
                                role,  # IS NOT NULL check
                                tuple(traits),  # IN check
                                tuple(traits),  # IN check
                                role,  # jsonb_array_elements
                                *ext_args,
                            ),
                        )
                    }
                )
            elif not allow_empty_traits:
                qs = qs.annotate(**{f"has_role_{i}": Value(False)})
            else:
                qs = qs.annotate(
                    **{
                        f"has_role_{i}": RawSQL(
                            """(
                                trait_grants ? %s AND
                                trait_grants->%s IS NOT NULL AND
                                jsonb_array_length(trait_grants->%s) = 0
                            )""",
                            (
                                role,  # ? check
                                role,  # IS NOT NULL check
                                role,  # jsonb_array_length
                            ),
                        )
                    }
                )
            requirements |= Q(**{f"has_role_{i}": True})

        return qs.filter(requirements, event=event)


class Room(VersionedModel, OrderedModel, PretalxModel):
    log_prefix = "pretalx.room"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    deleted = models.BooleanField(default=False)
    event = models.ForeignKey(
        to="eventyaybase.Event", on_delete=models.PROTECT, related_name="rooms"
    )
    name = I18nCharField(max_length=300, verbose_name=_("Name"))  # Increased to match room.py
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))  # Keep TextField for unlimited length

    # Pretalx-specific fields
    guid = models.UUIDField(
        null=True, blank=True, verbose_name=_("GUID"),
        help_text=_("Unique identifier (UUID) to help external tools identify the room.")
    )
    speaker_info = I18nCharField(
        max_length=1000, null=True, blank=True, verbose_name=_("Speaker Information"),
        help_text=_("Information relevant for speakers scheduled in this room, for example room size, special directions, available adaptors for video input …")
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Capacity"),
        help_text=_("How many people can fit in the room?")
    )
    position = models.PositiveIntegerField(null=True, blank=True)  # From OrderedModel

    # Video/interactive platform fields
    trait_grants = JSONField(null=True, blank=True, default=default_grants)
    module_config = JSONField(null=True, default=empty_module_config)
    picture = models.FileField(null=True, blank=True)
    sorting_priority = models.IntegerField(default=0)
    import_id = models.CharField(max_length=100, null=True, blank=True)
    pretalx_id = models.IntegerField(default=0)
    schedule_data = JSONField(null=True, blank=True)
    force_join = models.BooleanField(default=False)

    objects = RoomQuerySet.as_manager()

    class Meta:
        # WARNING: Conflicting ordering fields - both position and sorting_priority exist
        # Consider using only one for consistency
        ordering = ("position", "sorting_priority", "name")
        unique_together = ("event", "guid")
        # Note: VersionedModel, OrderedModel, PretalxModel may have conflicting Meta options
        rules_permissions = {
            "list": is_agenda_visible | orga_can_change_submissions,
            "view": is_agenda_visible | orga_can_change_submissions,
            "orga_list": orga_can_change_submissions,
            "orga_view": orga_can_change_submissions,
            "create": can_change_event_settings,
            "update": can_change_event_settings,
            "delete": can_change_event_settings,
        }

    class urls(EventUrls):
        settings_base = edit = "{self.event.orga_urls.room_settings}{self.pk}/"
        delete = "{settings_base}delete/"

    def __str__(self):
        return str(self.name)

    @property
    def log_parent(self):
        return self.event

    @staticmethod
    def get_order_queryset(event):
        return event.rooms.all()

    @cached_property
    def uuid(self):
        if self.guid:
            return self.guid
        if not self.pk:
            return ""
        return uuid.uuid5(GlobalSettings().get_instance_identifier(), f"room:{self.pk}")

    @property
    def slug(self):
        return f"{self.id}-{slugify(self.name)}"


class Reaction(models.Model):
    room = models.ForeignKey("Room", related_name="reactions", on_delete=models.CASCADE)
    datetime = models.DateTimeField(auto_now_add=True)
    reaction = models.CharField(max_length=100)
    amount = models.IntegerField()


class RoomView(models.Model):
    room = models.ForeignKey(to="Room", related_name="views", on_delete=models.CASCADE)
    start = models.DateTimeField(
        auto_now_add=True,
    )
    end = models.DateTimeField(
        null=True, db_index=True
    )  # index required for control/ dashboard
    user = models.ForeignKey(to="user", related_name="views", on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["start"]),
        ]


class RoomConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = (
            "id",
            "trait_grants",
            "module_config",
            "picture",
            "name",
            "description",
            "sorting_priority",
            "pretalx_id",
            "force_join",
            "schedule_data",
        )


def approximate_view_number(actual_number):
    if actual_number is None or actual_number < 1:
        return "none"
    elif actual_number > 10:
        return "many"
    else:
        return "few"


def generate_short_token():
    chars = "abcdefghijklmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ123456789"
    return get_random_string(6, chars)


class AnonymousInvite(models.Model):
    short_token = models.CharField(
        db_index=True,
        unique=True,
        default=generate_short_token,
        max_length=150,
    )
    event = models.ForeignKey(
        "eventyaybase.Event", related_name="anonymous_invites", on_delete=models.CASCADE
    )
    room = models.ForeignKey(
        "Room", related_name="anonymous_invites", on_delete=models.CASCADE
    )
    expires = models.DateTimeField()