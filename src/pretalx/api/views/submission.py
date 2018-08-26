from rest_framework import viewsets

from pretalx.api.serializers.submission import (
    ScheduleListSerializer, ScheduleSerializer, SubmissionSerializer,
)
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubmissionSerializer
    queryset = Submission.objects.none()
    lookup_field = 'code__iexact'
    filter_fields = ('state', 'content_locale', 'submission_type')
    search_fields = ('title', 'speakers__name')

    def get_base_queryset(self):
        if self.request.user.has_perm('orga.view_submissions', self.request.event):
            return self.request.event.submissions.all()
        if (
            not self.request.user.has_perm('agenda.view_schedule', self.request.event)
            or not self.request.event.current_schedule
        ):
            return Submission.objects.none()
        return self.request.event.submissions.filter(
            slots__in=self.request.event.current_schedule.talks.filter(is_visible=True)
        )

    def get_queryset(self):
        return self.get_base_queryset() or self.queryset


class TalkViewSet(SubmissionViewSet):
    def get_queryset(self):
        if (
            not self.request.user.has_perm('agenda.view_schedule', self.request.event)
            or not self.request.event.current_schedule
        ):
            return Submission.objects.none()
        return self.request.event.submissions.filter(
            slots__in=self.request.event.current_schedule.talks.filter(is_visible=True)
        )


class ScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleSerializer
    queryset = Schedule.objects.none()
    lookup_field = 'version__iexact'

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleListSerializer
        if self.action == 'retrieve':
            return ScheduleSerializer
        raise Exception('Methods other than GET are not supported on this ressource.')

    def get_object(self):
        try:
            return super().get_object()
        except Exception:
            is_public = (
                self.request.event.is_public
                and self.request.event.settings.show_schedule
            )
            has_perm = self.request.user.has_perm(
                'orga.edit_schedule', self.request.event
            )
            query = self.kwargs.get(self.lookup_field)
            if has_perm and query == 'wip':
                return self.request.event.wip_schedule
            if (
                (has_perm or is_public)
                and query == 'latest'
                and self.request.event.current_schedule
            ):
                return self.request.event.current_schedule
            raise

    def get_queryset(self):
        qs = self.queryset
        is_public = (
            self.request.event.is_public and self.request.event.settings.show_schedule
        )
        current_schedule = (
            self.request.event.current_schedule.pk
            if self.request.event.current_schedule
            else None
        )

        if self.request.user.has_perm('orga.view_schedule', self.request.event):
            return self.request.event.schedules.all()
        if is_public:
            return self.request.event.schedules.filter(pk=current_schedule)
        return qs
