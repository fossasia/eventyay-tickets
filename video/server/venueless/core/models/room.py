import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.db.models.expressions import RawSQL
from rest_framework import serializers

from venueless.core.models.cache import VersionedModel
from venueless.core.permissions import Permission


def empty_module_config():
    return []


def default_grants():
    return {
        "viewer": [],
    }


class RoomQuerySet(models.QuerySet):
    def with_permission(
        self, *, user=None, traits=None, world, permission=Permission.ROOM_VIEW
    ):
        from .auth import RoomGrant, WorldGrant

        traits = traits or user.traits
        if world.has_permission_implicit(traits=traits, permissions=[permission]):
            # User has the permission globally, nothing to do
            return self.all()

        # Get all roles that grant view access
        roles = [
            role
            for role, permissions in world.roles.items()
            if permission.value in permissions
        ]

        if not roles:  # pragma: no cover
            # No role grants access, impossible
            return self.none()

        if user:
            sq_user_has_room_grant = RoomGrant.objects.filter(
                user=user, world=world, room_id=OuterRef("pk"), role__in=roles
            )
            sq_user_has_world_grant = WorldGrant.objects.filter(
                user=user, world=world, role__in=roles
            )
            qs = self.annotate(
                user_has_room_grant=Exists(sq_user_has_room_grant),
                user_has_world_grant=Exists(sq_user_has_world_grant),
            )
            requirements = Q(user_has_room_grant=True) | Q(user_has_world_grant=True)
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
        # In case it is an empty array, everyone is permitted. When our user has traits, this is automatically ensured
        # by the ALL() statement, but when traits=[] we need to do a special case check since "IN ()" is not valid SQL
        for i, role in enumerate(roles):
            if traits:
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
                            )
                        )""",
                            (
                                role,  # ? check
                                role,  # IS NOT NULL check
                                tuple(traits),  # IN check
                                tuple(traits),  # IN check
                                role,  # jsonb_array_elements
                            ),
                        )
                    }
                )
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

        qs = qs.filter(
            requirements,
            world=world,
        )
        return qs


class Room(VersionedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    deleted = models.BooleanField(default=False)
    world = models.ForeignKey(
        to="core.World", related_name="rooms", on_delete=models.PROTECT
    )
    trait_grants = JSONField(null=True, blank=True, default=default_grants)
    module_config = JSONField(null=True, default=empty_module_config)
    name = models.CharField(max_length=300)
    description = models.TextField(null=True, blank=True)
    picture = models.FileField(null=True, blank=True)
    sorting_priority = models.IntegerField(default=0)
    import_id = models.CharField(max_length=100, null=True, blank=True)
    pretalx_id = models.IntegerField(default=0)
    schedule_data = JSONField(null=True, blank=True)
    force_join = models.BooleanField(default=False)

    objects = RoomQuerySet.as_manager()

    class Meta:
        ordering = ("sorting_priority", "name")


class Reaction(models.Model):
    room = models.ForeignKey(
        to="Room", related_name="reactions", on_delete=models.CASCADE
    )
    datetime = models.DateTimeField(auto_now_add=True)
    reaction = models.CharField(max_length=100)
    amount = models.IntegerField()


class RoomView(models.Model):
    room = models.ForeignKey(to="Room", related_name="views", on_delete=models.CASCADE)
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(
        null=True, db_index=True
    )  # index required for control/ dashboard
    user = models.ForeignKey(to="user", related_name="views", on_delete=models.CASCADE)


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
