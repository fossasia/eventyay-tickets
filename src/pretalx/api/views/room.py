from rest_framework import viewsets

from pretalx.api.serializers.room import RoomOrgaSerializer, RoomSerializer
from pretalx.schedule.models import Room


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Room.objects.none()

    def get_queryset(self):
        if self.request.user.has_perm('agenda.view_schedule', self.request.event):
            return self.request.event.rooms.all()
        return self.request.event.rooms.none()

    def get_serializer_class(self):
        if self.request.user.has_perm('orga.edit_room', self.request.event):
            return RoomOrgaSerializer
        return RoomSerializer
