from django.utils.functional import cached_property
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import SAFE_METHODS

from pretalx.api.documentation import build_expand_docs, build_search_docs
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.legacy import (
    LegacySpeakerOrgaSerializer,
    LegacySpeakerReviewerSerializer,
    LegacySpeakerSerializer,
)
from pretalx.api.serializers.speaker import (
    SpeakerOrgaSerializer,
    SpeakerSerializer,
    SpeakerUpdateSerializer,
)
from pretalx.api.versions import LEGACY
from pretalx.person.models import SpeakerProfile
from pretalx.submission.rules import (
    questions_for_user,
    speaker_profiles_for_user,
    submissions_for_user,
)


class SpeakerSearchFilter(filters.SearchFilter):
    def get_search_fields(self, view, request):
        if view.is_orga:
            return ("user__fullname", "user__email")
        return ("user__fullname",)


@extend_schema_view(
    list=extend_schema(
        summary="List Speakers",
        parameters=[
            build_search_docs(
                "name",
                extra_description="Organiser search also includes email addresses.",
            ),
            build_expand_docs("submissions", "answers", "answers.question"),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Speaker",
        parameters=[
            build_expand_docs("submissions", "answers", "answers.question"),
        ],
    ),
    update=extend_schema(
        summary="Update Speaker",
        request=SpeakerUpdateSerializer,
        responses={200: SpeakerOrgaSerializer},
    ),
    partial_update=extend_schema(
        summary="Update Speaker (Partial Update)",
        request=SpeakerUpdateSerializer,
        responses={200: SpeakerOrgaSerializer},
    ),
)
class SpeakerViewSet(
    PretalxViewSetMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SpeakerSerializer
    queryset = SpeakerProfile.objects.none()
    lookup_field = "user__code__iexact"
    search_fields = ("user__fullname", "user__email")
    endpoint = "speakers"
    filter_backends = (SpeakerSearchFilter, DjangoFilterBackend)

    def get_legacy_serializer_class(self):  # pragma: no cover
        if self.request.user.has_perm("submission.orga_update_submission", self.event):
            return LegacySpeakerOrgaSerializer
        if self.request.user.has_perm("person.orga_list_speakerprofile", self.event):
            return LegacySpeakerReviewerSerializer
        return LegacySpeakerSerializer

    def get_legacy_queryset(self):  # pragma: no cover
        if self.request.user.has_perm("person.orga_list_speakerprofile", self.event):
            return SpeakerProfile.objects.filter(event=self.event, user__isnull=False)
        if self.event.current_schedule and self.event.get_feature_flag("show_schedule"):
            return SpeakerProfile.objects.filter(
                event=self.event,
                user__submissions__pk__in=self.event.current_schedule.talks.all().values_list(
                    "submission_id", flat=True
                ),
            ).distinct()
        return SpeakerProfile.objects.none()

    def get_serializer(self, *args, **kwargs):
        if self.api_version == LEGACY:  # pragma: no cover
            kwargs["questions"] = (
                self.request.query_params.get("questions") or ""
            ).split(",")
        return super().get_serializer(*args, **kwargs)

    @cached_property
    def is_orga(self):
        return self.event and self.request.user.has_perm(
            "submission.orga_list_submission", self.event
        )

    def get_unversioned_serializer_class(self):
        if self.api_version == LEGACY:  # pragma: no cover
            return self.get_legacy_serializer_class()
        if self.is_orga:
            if self.request.method not in SAFE_METHODS:
                return SpeakerUpdateSerializer
            return SpeakerOrgaSerializer
        return SpeakerSerializer

    @cached_property
    def submissions_for_user(self):
        return submissions_for_user(self.event, self.request.user).select_related(
            "event"
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not self.event:
            return context
        context["questions"] = questions_for_user(self.event, self.request.user)
        # We don’t need to check for anonymisation here, because endpoint access implies
        # that the user isn’t restricted to anonymised content.
        context["submissions"] = self.submissions_for_user
        return context

    def get_queryset(self):
        if self.api_version == LEGACY:  # pragma: no cover
            queryset = self.get_legacy_queryset() or self.queryset
            return queryset.select_related("user", "event", "event__cfp")
        if not self.event:
            # This is just during api doc creation
            return self.queryset
        queryset = (
            speaker_profiles_for_user(
                self.event, self.request.user, submissions=self.submissions_for_user
            )
            .select_related("user", "event")
            .prefetch_related("user__submissions", "user__answers")
            .order_by("pk")
        )
        if fields := self.check_expanded_fields(
            "answers.question",
            "answers.question.tracks",
            "answers.question.submission_types",
            "submissions",
            "submissions.track",
            "submissions.submission_type",
        ):
            prefetches = [f"user__{field.replace('.', '__')}" for field in fields]
            queryset = queryset.prefetch_related(*prefetches)
        return queryset
