from django.utils.functional import cached_property
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS

from pretalx.api.documentation import build_expand_docs, build_search_docs
from pretalx.api.filters.review import ReviewFilter
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.review import ReviewSerializer, ReviewWriteSerializer
from pretalx.submission.models import Review, Submission
from pretalx.submission.rules import get_reviewable_submissions


@extend_schema_view(
    list=extend_schema(
        summary="List Reviews",
        parameters=[
            build_search_docs("submission.title", "user.name"),
            build_expand_docs(
                "user",
                "scores.category",
                "submission",
                "submission.speakers",
                "submission.track",
                "submission.submission_type",
                "submission.tags",
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Review",
        parameters=[
            build_expand_docs("user", "submission", "scores.category"),
        ],
    ),
    create=extend_schema(
        summary="Create Review",
        request=ReviewWriteSerializer,
        responses={201: ReviewSerializer},
    ),
    update=extend_schema(
        summary="Update Reviews",
        request=ReviewWriteSerializer,
        responses={200: ReviewSerializer},
    ),
    partial_update=extend_schema(
        summary="Update Reviews (Partial Update)",
        request=ReviewWriteSerializer,
        responses={200: ReviewSerializer},
    ),
    destroy=extend_schema(summary="Delete Reviews"),
)
class ReviewViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    queryset = Review.objects.none()
    search_fields = ("submission__title", "user__fullname")
    filterset_class = ReviewFilter
    endpoint = "reviews"
    # We only permit access to this endpoint if the user can see all reviews,
    # as otherwise we would potentially have to filter for reviews to submissions
    # that the user has reviewed already.
    permission_map = {"list": "submission.list_all_review"}

    def get_unversioned_serializer_class(self):
        if self.request.method not in SAFE_METHODS:
            return ReviewWriteSerializer
        return ReviewSerializer

    @cached_property
    def visible_submissions(self):
        if not self.event:
            return Submission.objects.none()
        submissions = self.event.submissions.all().exclude(
            speakers__in=[self.request.user]
        )
        return get_reviewable_submissions(self.event, self.request.user, submissions)

    def get_queryset(self):
        if not self.event or self.request.user.is_anonymous:
            # This happens only during API doc generation
            return Review.objects.none()

        queryset = (
            Review.objects.filter(
                submission__event=self.request.event,
                submission__in=self.visible_submissions,
            )
            .select_related(
                "submission",
            )
            .prefetch_related("scores", "scores__category")
            .order_by("pk")
        )
        if fields := self.check_expanded_fields(
            "submission.track", "submission.submission_type", "user"
        ):
            queryset = queryset.select_related(
                *[field.replace(".", "__") for field in fields]
            )
        if fields := self.check_expanded_fields(
            "submission.tags", "submission.assigned_reviewers", "submission.speakers"
        ):
            queryset = queryset.prefetch_related(
                *[field.replace(".", "__") for field in fields]
            )
        return queryset

    def get_serializer_context(self):
        result = super().get_serializer_context()
        result["submissions"] = self.visible_submissions
        return result
