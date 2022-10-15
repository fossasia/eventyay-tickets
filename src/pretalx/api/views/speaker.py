from django.utils.functional import cached_property
from rest_framework import viewsets

from pretalx.api.serializers.speaker import (
    SpeakerOrgaSerializer,
    SpeakerReviewerSerializer,
    SpeakerSerializer,
)
from pretalx.person.models import SpeakerProfile


class SpeakerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SpeakerSerializer
    queryset = SpeakerProfile.objects.none()
    lookup_field = "user__code__iexact"
    filterset_fields = ("user__name", "user__email")
    search_fields = ("user__name", "user__email")

    @cached_property
    def serializer_questions(self):
        return (self.request.query_params.get("questions") or "").split(",")

    def get_serializer_class(self):
        if self.request.user.has_perm("orga.change_submissions", self.request.event):
            return SpeakerOrgaSerializer
        if self.request.user.has_perm("orga.view_speakers", self.request.event):
            return SpeakerReviewerSerializer
        return SpeakerSerializer

    def get_serializer(self, *args, **kwargs):
        return super().get_serializer(
            *args,
            questions=self.serializer_questions,
            **kwargs,
        )

    def get_base_queryset(self):
        if self.request.user.has_perm("orga.view_speakers", self.request.event):
            return SpeakerProfile.objects.filter(
                event=self.request.event, user__isnull=False
            )
        if (
            self.request.event.current_schedule
            and self.request.event.feature_flags["show_schedule"]
        ):
            return SpeakerProfile.objects.filter(
                event=self.request.event,
                user__submissions__pk__in=self.request.event.current_schedule.talks.all().values_list(
                    "submission_id", flat=True
                ),
            ).distinct()
        return SpeakerProfile.objects.none()

    def get_queryset(self):
        return self.get_base_queryset() or self.queryset
