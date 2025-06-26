from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from pretalx.api.documentation import build_expand_docs, build_search_docs
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.speaker_information import SpeakerInformationSerializer
from pretalx.person.models import SpeakerInformation


@extend_schema_view(
    list=extend_schema(
        summary="List Speaker Information",
        parameters=[
            build_search_docs("title"),
            build_expand_docs("limit_tracks", "limit_types"),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Speaker Information",
        parameters=[build_expand_docs("limit_tracks", "limit_types")],
    ),
    create=extend_schema(summary="Create Speaker Information"),
    update=extend_schema(summary="Update Speaker Information"),
    partial_update=extend_schema(summary="Update Speaker Information (Partial Update)"),
    destroy=extend_schema(summary="Delete Speaker Information"),
)
class SpeakerInformationViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SpeakerInformationSerializer
    queryset = SpeakerInformation.objects.none()
    endpoint = "speaker-information"
    search_fields = ("title",)
    permission_map = {"retrieve": "person.orga_view_speakerinformation"}

    def get_queryset(self):
        queryset = self.event.information.all().select_related("event").order_by("pk")
        if fields := self.check_expanded_fields("limit_tracks", "limit_types"):
            queryset = queryset.prefetch_related(*fields)
        return queryset
