from rest_framework import viewsets

from pretalx.api.serializers.review import ReviewSerializer
from pretalx.submission.models import Review


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReviewSerializer
    queryset = Review.objects.none()
    filterset_fields = ('submission__code',)

    def get_queryset(self):
        if not self.request.user.has_perm(
            'submission.view_reviews', self.request.event
        ):
            return Review.objects.none()
        return Review.objects.filter(submission__event=self.request.event).exclude(
            submission__speakers__in=[self.request.user]
        )
