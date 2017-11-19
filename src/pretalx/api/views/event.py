from rest_framework import viewsets

from pretalx.api.serializers.event import EventSerializer
from pretalx.event.models import Event


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EventSerializer
    queryset = Event.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'event'
    pagination_class = None

    def get_queryset(self):
        return [e for e in Event.objects.all() if self.request.user.has_perm('cfp.view_event', e)]
