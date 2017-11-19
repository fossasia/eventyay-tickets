from rest_framework import viewsets

from pretalx.api.serializers.submission import (
    ScheduleSerializer, SubmissionSerializer,
)
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission, SubmissionStates


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubmissionSerializer
    queryset = Submission.objects.none()
    lookup_field = 'code__iexact'

    def get_base_queryset(self):
        if self.request.user.has_perm('orga.view_submissions', self.request.event):
            return self.request.event.submissions.all()
        if self.request.event.current_schedule:
            return self.request.event.submissions.filter(slots__in=self.request.event.current_schedule.talks.all())

    def get_queryset(self):
        qs = self.get_base_queryset() or self.queryset
        if 'talks' in self.request._request.path:
            qs = qs.filter(state=SubmissionStates.CONFIRMED)
        return qs


class ScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleSerializer
    queryset = Schedule.objects.none()
    lookup_field = 'version'
    """ TODO: implement /current """

    def get_queryset(self):
        qs = self.queryset
        is_public = self.request.event.is_public and self.request.event.settings.show_schedule

        if self.request.user.has_perm('orga.view_schedule', self.request.event):
            return self.request.event.schedules.all()
        if is_public:
            return self.request.event.schedules.filter(version__isnull=False)
        return qs
