from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from pretalx.agenda.views.utils import get_schedule_exporter_content
from pretalx.api.documentation import build_expand_docs, build_search_docs
from pretalx.api.filters.schedule import TalkSlotFilter
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.legacy import LegacyScheduleSerializer
from pretalx.api.serializers.schedule import (
    ScheduleListSerializer,
    ScheduleReleaseSerializer,
    ScheduleSerializer,
    TalkSlotOrgaSerializer,
    TalkSlotSerializer,
)
from pretalx.schedule.models import Schedule, TalkSlot


@extend_schema_view(
    list=extend_schema(
        summary="List Schedules",
        description=(
            "This endpoint returns a list of schedules. "
            "As schedule data can get very complex when expanded, the list endpoint only contains metadata. "
            "Please refer to the detail endpoint documentation to see how to retrieve slots, submissions and speakers."
        ),
        parameters=[build_search_docs("version")],
    ),
    retrieve=extend_schema(
        summary="Show Schedule",
        description=(
            "In addition to the standard lookup by ID, you can also use the special /wip/ and /latest/ URL paths to access the unpublished and latest published schedules. "
            "To receive most schedule data, query the endpoint with ``?expand=room,slots.submission.speakers``."
        ),
        parameters=[
            build_expand_docs(
                "slots",
                "slots.room",
                "slots.submission",
                "slots.submission.speakers",
                "slots.submission.track",
                "slots.submission.submission_type",
            ),
        ],
    ),
)
class ScheduleViewSet(PretalxViewSetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = LegacyScheduleSerializer
    queryset = Schedule.objects.none()
    endpoint = "schedules"
    search_fields = ("version",)
    # We look up schedules by IDs, but we permit the special names "wip" and "latest"
    lookup_value_regex = "[^/]+"
    permission_map = {
        "redirect_version": "schedule.list_schedule",
        "get_exporter": "schedule.list_schedule",
    }

    def get_unversioned_serializer_class(self):
        if self.action == "list":
            return ScheduleListSerializer
        if self.action == "release":
            return ScheduleReleaseSerializer
        return ScheduleSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["only_visible_slots"] = self.event and not self.has_perm("orga_view")
        return context

    def get_queryset(self):
        if not self.event:
            return self.queryset
        current_schedule = (
            self.event.current_schedule.pk if self.event.current_schedule else None
        )
        if self.has_perm("release", self.event):
            return self.event.schedules.all()
        return self.event.schedules.filter(pk=current_schedule)

    def get_object(self):
        identifier = self.kwargs.get(self.lookup_field)
        if identifier == "wip":
            queryset = self.get_queryset()
            obj = get_object_or_404(queryset, version=None)
            self.check_object_permissions(self.request, obj)
            return obj
        if identifier == "latest":
            if not self.event or not self.event.current_schedule:
                raise Http404
            obj = get_object_or_404(
                self.get_queryset(), pk=self.event.current_schedule.pk
            )
            self.check_object_permissions(self.request, obj)
            return obj

        return super().get_object()

    @extend_schema(
        summary="Redirect to a schedule by its version",
        description="This endpoint redirects to a specific schedule using its version name (e.g., '1.0', 'My Release') instead of its numeric ID.",
        parameters=[
            OpenApiParameter(
                name="version",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="The version string/name of the schedule (e.g., '1.0', 'Final Version').",
            )
        ],
        responses={
            302: OpenApiResponse(),
            404: OpenApiResponse(),
        },
    )
    @action(detail=False, url_path="by-version")
    def redirect_version(self, request, event):
        version = request.query_params.get("version")
        schedule = get_object_or_404(self.event.schedules, version=version)
        if not self.has_perm("view", schedule):
            raise Http404
        redirect_url = reverse(
            "api:schedule-detail", kwargs={"event": event, "pk": schedule.pk}
        )
        return HttpResponseRedirect(redirect_url)

    @extend_schema(
        summary="Release a new schedule version",
        description="Freezes the current Work-in-Progress (WIP) schedule, creating a new named version. This makes the WIP schedule available under the given version name and creates a new empty WIP schedule.",
        request=ScheduleReleaseSerializer,
        responses={
            201: OpenApiResponse(
                description="Schedule released successfully.",
                response=ScheduleSerializer,
            ),
            400: OpenApiResponse(
                description="Invalid data provided (e.g., version name already exists)."
            ),
            403: OpenApiResponse(description="Permission denied."),
        },
    )
    @action(detail=False, methods=["POST"])
    def release(self, request, event):
        wip_schedule = request.event.wip_schedule
        serializer = ScheduleReleaseSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        version_name = serializer.validated_data.get("version")
        comment = serializer.validated_data.get("comment")

        schedule, _ = wip_schedule.freeze(
            name=version_name,
            user=request.user,
            notify_speakers=False,
            comment=comment,
        )

        response_serializer = ScheduleSerializer(
            schedule, context=self.get_serializer_context()
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get Exporter Content",
        description="Retrieve the content of a specific schedule exporter by name.",
        parameters=[
            OpenApiParameter(
                name="name",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="The name of the exporter.",
            ),
            OpenApiParameter(
                name="lang",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Language code for the export content.",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Format depends on the chosen exporter."),
            404: OpenApiResponse(description="Exporter or schedule not found."),
        },
    )
    @action(detail=True, methods=["get"], url_path="exporters/(?P<name>[^/]+)")
    def get_exporter(self, request, event, pk=None, name=None):
        schedule = self.get_object()
        response = get_schedule_exporter_content(request, name, schedule)
        if not response:
            raise Http404()
        return response


@extend_schema_view(
    list=extend_schema(
        summary="List Talk Slots",
        description="This endpoint always returns a filtered list. If you don’t provide any filters of your own, it will be filtered to show only talk slots in the latest published schedule.",
        parameters=[
            build_search_docs("submission.title", "submission.speakers.name"),
            build_expand_docs(
                "room",
                "schedule",
                "submission",
                "submission.speakers",
                "submission.track",
                "submission.submission_type",
                "submission.answers",
                "submission.answers.question",
                "submission.resources",
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Talk Slot",
        parameters=[
            build_expand_docs(
                "room",
                "schedule",
                "submission",
                "submission.speakers",
                "submission.track",
                "submission.submission_type",
                "submission.answers",
                "submission.answers.question",
                "submission.resources",
            )
        ],
    ),
    update=extend_schema(
        summary="Update Talk Slot",
        description="Only talk slots in the WIP schedule can be changed – once a schedule version is frozen, its talk slots can’t be modified anymore.",
    ),
    partial_update=extend_schema(
        summary="Update Talk Slot (Partial Update)",
        description="Only talk slots in the WIP schedule can be changed – once a schedule version is frozen, its talk slots can’t be modified anymore.",
    ),
    ical=extend_schema(summary="Export Talk Slot as iCalendar file"),
)
class TalkSlotViewSet(
    PretalxViewSetMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TalkSlotSerializer
    queryset = TalkSlot.objects.none()
    endpoint = "slots"
    search_fields = ("submission__title", "submission__speakers__name")
    filterset_class = TalkSlotFilter
    permission_map = {"ical": "schedule.view_talkslot"}

    @cached_property
    def is_orga(self):
        return self.event and self.request.user.has_perm(
            "schedule.orga_view_schedule", self.event
        )

    def get_unversioned_serializer_class(self):
        if self.is_orga:
            return TalkSlotOrgaSerializer
        return TalkSlotSerializer

    def get_queryset(self):
        if not self.event:
            return self.queryset

        queryset = TalkSlot.objects.filter(schedule__event=self.event).select_related(
            "submission", "room", "schedule"
        )
        if not self.is_orga:
            queryset = queryset.filter(is_visible=True).exclude(
                schedule__version__isnull=True
            )

        if fields := self.check_expanded_fields(
            "submission.speakers",
            "submission.resources",
            "submission.answers",
            "submission.question",
        ):
            queryset = queryset.prefetch_related(
                *[f.replace(".", "__") for f in fields]
            )
        if fields := self.check_expanded_fields(
            "submission.track", "submission.submission_type"
        ):
            queryset = queryset.select_related(*[f.replace(".", "__") for f in fields])

        if self.action != "list":
            return queryset

        # In the list view, fall back to filtering by current schedule if there is no
        # other filter present.
        # If there is no current schedule, that means an empty response.
        filter_params = self.filterset_class.get_fields().keys()
        is_any_filter_active = any(
            param in self.request.query_params for param in filter_params
        )

        if not is_any_filter_active:
            queryset = queryset.filter(schedule=self.event.current_schedule)

        return queryset

    @action(detail=True, methods=["get"])
    def ical(self, request, event, pk=None):
        """Export a single talk slot as an iCalendar file."""
        slot = self.get_object()
        if not slot.submission:
            raise Http404
        calendar_data = slot.full_ical()
        response = HttpResponse(calendar_data.serialize(), content_type="text/calendar")
        response["Content-Disposition"] = (
            f'attachment; filename="{request.event.slug}-{slot.submission.code}.ics"'
        )
        return response
