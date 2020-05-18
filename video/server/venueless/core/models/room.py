import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import Exists, OuterRef, Q

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
        if world.has_permission_implicit(traits=traits, permission=permission):
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

        # Implicit role grants
        for role in roles:
            requirements |= Q(
                Q(
                    **{
                        "trait_grants__has_key": role,
                        f"trait_grants__{role}__contained_by": user.traits,
                    }
                )
                & ~Q(**{f"trait_grants__{role}": None,})
            )

        return qs.filter(requirements, world=world,)


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
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

    objects = RoomQuerySet.as_manager()

    class Meta:
        ordering = ("sorting_priority", "name")
