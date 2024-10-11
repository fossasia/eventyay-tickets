from django.db.models import Count
from django.http import Http404
from django.utils.functional import cached_property
from django_filters import rest_framework as filters
from django_scopes import scopes_disabled
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from pretalx.api.serializers.submission import (
    ScheduleListSerializer,
    ScheduleSerializer,
    SubmissionOrgaSerializer,
    SubmissionReviewerSerializer,
    SubmissionSerializer,
    TagSerializer,
)
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission, SubmissionStates, Tag

with scopes_disabled():

    class SubmissionFilter(filters.FilterSet):
        state = filters.MultipleChoiceFilter(choices=SubmissionStates.get_choices())

        class Meta:
            model = Submission
            fields = ("state", "content_locale", "submission_type", "is_featured")


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubmissionSerializer
    queryset = Submission.objects.none()
    lookup_field = "code__iexact"
    search_fields = ("title", "speakers__name")
    filterset_class = SubmissionFilter
    permission_map = {
        "favourite": "agenda.view_schedule",
        "favourite_object": "agenda.view_submission",
    }

    def get_queryset(self):
        base_qs = self.request.event.submissions.all().annotate(
            favourite_count=Count("favourites")
        )
        if self.request._request.path.endswith(
            "/talks/"
        ) or not self.request.user.has_perm(
            "orga.view_submissions", self.request.event
        ):
            if (
                not self.request.user.has_perm(
                    "agenda.view_schedule", self.request.event
                )
                or not self.request.event.current_schedule
            ):
                return Submission.objects.none()
            return base_qs.filter(
                pk__in=self.request.event.current_schedule.talks.filter(
                    is_visible=True
                ).values_list("submission_id", flat=True)
            )
        return base_qs

    def get_serializer_class(self):
        if self.request.user.has_perm("orga.change_submissions", self.request.event):
            return SubmissionOrgaSerializer
        if self.request.user.has_perm("orga.view_submissions", self.request.event):
            return SubmissionReviewerSerializer
        return SubmissionSerializer

    @cached_property
    def serializer_questions(self):
        return (self.request.query_params.get("questions") or "").split(",")

    def get_serializer(self, *args, **kwargs):
        can_view_speakers = self.request.user.has_perm(
            "agenda.view_schedule", self.request.event
        ) or self.request.user.has_perm("orga.view_speakers", self.request.event)
        if self.request.query_params.get("anon"):
            can_view_speakers = False
        return super().get_serializer(
            *args,
            can_view_speakers=can_view_speakers,
            event=self.request.event,
            questions=self.serializer_questions,
            **kwargs,
        )

    @action(detail=False, methods=["GET"])
    def favourites(self, request, **kwargs):
        if not request.user.is_authenticated:
            raise Http404
        # Return ical file if accept header is set to text/calendar
        if request.accepted_renderer.format == "ics":
            return self.favourites_ical(request)
        return Response(
            [
                sub.code
                for sub in Submission.objects.filter(
                    favourites__user__in=[request.user], event=request.event
                )
            ]
        )

    @action(detail=True, methods=["POST", "DELETE"])
    def favourite(self, request, **kwargs):
        if not request.user.is_authenticated:
            raise Http404
        submission = self.get_object()
        if request.method == "POST":
            submission.add_favourite(request.user)
        elif request.method == "DELETE":
            submission.remove_favourite(request.user)
        return Response({})


class ScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleSerializer
    queryset = Schedule.objects.none()
    lookup_value_regex = "[^/]+"

    def get_serializer_class(self):
        if self.action == "list":
            return ScheduleListSerializer
        return ScheduleSerializer  # self.action == 'retrieve'

    def get_object(self):
        schedules = self.get_queryset()
        query = self.kwargs.get(self.lookup_field)
        if query == "wip":
            schedule = schedules.filter(version__isnull=True).first()
        else:
            if query == "latest" and self.request.event.current_schedule:
                query = self.request.event.current_schedule.version
            schedule = schedules.filter(version__iexact=query).first()
        if not schedule:
            raise Http404
        return schedule

    def get_queryset(self):
        qs = self.queryset
        is_public = (
            self.request.event.is_public
            and self.request.event.get_feature_flag("show_schedule")
        )
        current_schedule = (
            self.request.event.current_schedule.pk
            if self.request.event.current_schedule
            else None
        )
        if self.request.user.has_perm("orga.view_schedule", self.request.event):
            return self.request.event.schedules.all()
        if is_public:
            return self.request.event.schedules.filter(pk=current_schedule)
        return qs


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.none()
    lookup_field = "tag__iexact"

    def get_queryset(self):
        if self.request.user.has_perm("orga.view_submissions", self.request.event):
            return self.request.event.tags.all()
        return Tag.objects.none()
