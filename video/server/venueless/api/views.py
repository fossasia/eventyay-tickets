from contextlib import suppress
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.core import exceptions
from django.db import transaction
from django.utils.timezone import now
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from venueless.api.auth import (
    ApiAccessRequiredPermission,
    RoomPermissions,
    UserDeletePermissions,
    WorldPermissions,
)
from venueless.api.serializers import RoomSerializer, WorldSerializer
from venueless.core.models import Channel, User
from venueless.core.services.world import notify_schedule_change, notify_world_change

from ..core.models import Room


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.none()
    serializer_class = RoomSerializer
    permission_classes = [ApiAccessRequiredPermission & RoomPermissions]

    def get_queryset(self):
        return self.request.world.rooms.with_permission(
            traits=self.request.auth.get("traits"), world=self.request.world
        )

    def perform_create(self, serializer):
        serializer.save(world=self.request.world)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, world=self.request.world
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_world_change)(self.request.world.id)
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, world=self.request.world
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_world_change)(self.request.world.id)
        )

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        for m in instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.filter(room=instance, world=self.request.world).delete()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_world_change)(self.request.world.id)
        )


class WorldView(APIView):
    permission_classes = [ApiAccessRequiredPermission & WorldPermissions]

    def get(self, request, **kwargs):
        return Response(WorldSerializer(request.world).data)

    @transaction.atomic
    def patch(self, request, **kwargs):
        serializer = WorldSerializer(request.world, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_world_change)(request.world.id)
        )
        return Response(serializer.data)


def get_domain(path):
    if not path:
        return ""
    domain = urlparse(path).netloc
    if ":" in domain:
        domain = domain.split(":")[0]
    return domain.lower()


@api_view(http_method_names=["POST"])
@permission_classes([ApiAccessRequiredPermission])
def schedule_update(request, **kwargs):
    """POST endpoint to notify venueless that schedule data has changed.

    Optionally, the request may contain data for the ``pretalx`` field in the
    world config.
    """
    domain = get_domain(request.data.get("domain"))
    event = request.data.get("event")

    if not domain or not event:
        return Response("Missing fields in request.", status=401)

    pretalx_config = request.world.config.get("pretalx", {})
    if domain != get_domain(
        pretalx_config.get("domain")
    ) or event != pretalx_config.get("event"):
        return Response("Incorrect domain or event data", status=401)

    # We assume that only pretalx uses this endpoint
    request.world.config["pretalx"]["connected"] = True
    request.world.config["pretalx"]["pushed"] = now().isoformat()
    request.world.save()

    async_to_sync(notify_schedule_change)(request.world.id)
    return Response(status=200)


@api_view(http_method_names=["POST"])
@permission_classes([UserDeletePermissions])
def delete_user(request, **kwargs):
    """POST endpoint to soft-delete a user.

    This endpoint is called with a single POST parameter, 'user_id'."""
    user_id = request.data.get("user_id")
    if not user_id:
        return Response("Missing user ID.", status=401)

    user = None
    with suppress(exceptions.ValidationError):  # raised when user_id isn't a uid
        user = User.objects.filter(id=user_id, deleted=False).first()
    if not user:
        return Response(status=404)

    user.soft_delete()
    return Response(status=204)
