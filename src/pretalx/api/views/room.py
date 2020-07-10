from rest_framework import pagination, viewsets

from pretalx.api.serializers.room import RoomOrgaSerializer, RoomSerializer
from pretalx.schedule.models import Room


class RoomPagination(pagination.LimitOffsetPagination):
    default_limit = 100


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Room.objects.none()
    pagination_class = RoomPagination

    def get_queryset(self):
        if self.request.user.has_perm("agenda.view_schedule", self.request.event):
            return self.request.event.rooms.all()
        return self.request.event.rooms.none()

    def get_serializer_class(self):
        if self.request.user.has_perm("orga.edit_room", self.request.event):
            return RoomOrgaSerializer
        return RoomSerializer
