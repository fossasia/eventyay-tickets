from rest_framework import viewsets

from pretalx.api.serializers.speaker import SpeakerOrgaSerializer, SpeakerSerializer
from pretalx.person.models import SpeakerProfile


class SpeakerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SpeakerSerializer
    queryset = SpeakerProfile.objects.none()
    lookup_field = 'user__code__iexact'
    filter_fields = ('user__name',)
    search_fields = ('user__name',)

    def get_serializer_class(self):
        if self.request.user.has_perm('orga.view_speakers', self.request.event):
            return SpeakerOrgaSerializer
        return SpeakerSerializer

    def get_base_queryset(self):
        if self.request.user.has_perm('orga.view_submissions', self.request.event):
            return SpeakerProfile.objects.filter(event=self.request.event)
        if (
            self.request.event.current_schedule
            and self.request.event.settings.show_schedule
        ):
            return SpeakerProfile.objects.filter(
                user__submissions__slots__in=self.request.event.current_schedule.talks.all()
            )
        return SpeakerProfile.objects.none()

    def get_queryset(self):
        return self.get_base_queryset() or self.queryset
