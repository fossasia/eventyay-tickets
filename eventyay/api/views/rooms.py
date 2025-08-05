from asgiref.sync import async_to_sync
from django.db import transaction
from rest_framework import viewsets

from eventyay.base.api.auth import (
    ApiAccessRequiredPermission,
    RoomPermissions,
)
from eventyay.api.serializers.rooms import RoomSerializer
from eventyay.base.models import Channel
from eventyay.base.models.room import Room
from eventyay.base.services.event import notify_event_change


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.none()
    serializer_class = RoomSerializer
    permission_classes = [ApiAccessRequiredPermission & RoomPermissions]

    def get_queryset(self):
        return self.request.event.rooms.with_permission(
            traits=self.request.auth.get("traits"), event=self.request.event
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, event=self.request.event
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, event=self.request.event
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        for m in instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.filter(room=instance, event=self.request.event).delete()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )