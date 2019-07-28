from django.db import models
from rest_framework import viewsets

from pretalx.api.serializers.review import ReviewSerializer
from pretalx.submission.models import Review
from pretalx.submission.models.submission import SubmissionStates


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReviewSerializer
    queryset = Review.objects.none()
    filterset_fields = ('submission__code',)

    def get_queryset(self):
        if not self.request.user.has_perm('orga.view_reviews', self.request.event):
            return Review.objects.none()
        queryset = Review.objects.filter(submission__event=self.request.event).exclude(
            submission__speakers__in=[self.request.user]
        ).exclude(submission__state=SubmissionStates.DELETED)
        limit_tracks = self.request.user.teams.filter(
            models.Q(all_events=True)
            | models.Q(
                models.Q(all_events=False)
                & models.Q(limit_events__in=[self.request.event])
            ),
            limit_tracks__isnull=False,
        )
        if limit_tracks.exists():
            tracks = set()
            for team in limit_tracks:
                tracks.update(team.limit_tracks.filter(event=self.request.event))
            queryset = queryset.filter(submission__track__in=tracks)
        return queryset.order_by('created')
