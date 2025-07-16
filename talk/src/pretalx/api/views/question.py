from django.db import transaction
from django.db.models.deletion import ProtectedError
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import exceptions, viewsets
from rest_framework.permissions import SAFE_METHODS

from pretalx.api.documentation import build_expand_docs, build_search_docs
from pretalx.api.mixins import PretalxViewSetMixin
from pretalx.api.serializers.question import (
    AnswerCreateSerializer,
    AnswerOptionCreateSerializer,
    AnswerOptionSerializer,
    AnswerSerializer,
    QuestionOrgaSerializer,
    QuestionSerializer,
)
from pretalx.submission.models import Answer, AnswerOption, Question, QuestionVariant
from pretalx.submission.rules import questions_for_user

OPTIONS_HELP = (
    "Please note that any update to the options field will delete the "
    "existing question options (if still possible) and replace them with the new ones. "
    "Use the AnswerOption API for granular question option modifications."
)


@extend_schema_view(
    list=extend_schema(
        summary="List Questions",
        parameters=[
            build_search_docs("question"),
            build_expand_docs("options", "tracks", "submission_types"),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Question",
        parameters=[build_expand_docs("options", "tracks", "submission_types")],
    ),
    create=extend_schema(summary="Create Question"),
    update=extend_schema(summary="Update Question", description=OPTIONS_HELP),
    partial_update=extend_schema(
        summary="Update Question (Partial Update)", description=OPTIONS_HELP
    ),
    destroy=extend_schema(summary="Delete Question"),
)
class QuestionViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    queryset = Question.objects.none()
    serializer_class = QuestionSerializer
    filterset_fields = ("is_public", "is_visible_to_reviewers", "target", "variant")
    search_fields = ("question",)
    endpoint = "questions"

    def get_queryset(self):
        queryset = questions_for_user(self.event, self.request.user).select_related(
            "event"
        )
        if fields := self.check_expanded_fields(
            "tracks", "submission_types", "options"
        ):
            queryset = queryset.prefetch_related(*fields)
        return queryset

    def get_unversioned_serializer_class(self):
        if self.request.method not in SAFE_METHODS or self.has_perm("update"):
            return QuestionOrgaSerializer
        return self.serializer_class

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                instance.options.all().delete()
                instance.logged_actions().delete()
                return super().perform_destroy(instance)
        except ProtectedError:
            raise exceptions.ValidationError(
                "You cannot delete a question object that has answers."
            )


@extend_schema_view(
    list=extend_schema(
        summary="List Question Options",
        parameters=[
            build_search_docs("answer"),
            build_expand_docs(
                "question", "question.tracks", "question.submission_types"
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Question Option",
        parameters=[
            build_expand_docs(
                "question", "question.tracks", "question.submission_types"
            )
        ],
    ),
    create=extend_schema(summary="Create Question Option"),
    update=extend_schema(summary="Update Question Option"),
    partial_update=extend_schema(summary="Update Question Option (Partial Update)"),
    destroy=extend_schema(
        summary="Delete Question Option",
        description="Deleting a question option is only possible if it hasn't been used in any answers yet.",
    ),
)
class AnswerOptionViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    queryset = AnswerOption.objects.none()
    serializer_class = AnswerOptionSerializer
    filterset_fields = ("question",)
    search_fields = ("answer",)
    endpoint = "question-options"

    def get_queryset(self):
        questions = questions_for_user(self.event, self.request.user)
        queryset = AnswerOption.objects.filter(
            question__in=questions,
            question__variant__in=[QuestionVariant.CHOICES, QuestionVariant.MULTIPLE],
        ).select_related("question", "question__event")
        for field in self.check_expanded_fields(
            "question.tracks", "question.submission_types"
        ):
            queryset = queryset.prefetch_related(field.replace(".", "__"))
        return queryset

    def get_unversioned_serializer_class(self):
        if self.action == "create":
            return AnswerOptionCreateSerializer
        return self.serializer_class

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                instance.logged_actions().delete()
                return super().perform_destroy(instance)
        except ProtectedError:
            raise exceptions.ValidationError(
                "You cannot delete an option object that has been used in answers."
            )


class AnswerFilterSet(filters.FilterSet):
    question = filters.NumberFilter(field_name="question_id")
    submission = filters.CharFilter(
        field_name="submission__code",
        lookup_expr="iexact",
    )
    person = filters.CharFilter(
        field_name="person__code",
        lookup_expr="iexact",
    )
    review = filters.NumberFilter(field_name="review_id")

    class Meta:
        model = Answer
        fields = ("question", "submission", "person", "review")


@extend_schema_view(
    list=extend_schema(
        summary="List Answers",
        parameters=[
            build_search_docs("answer"),
            build_expand_docs(
                "question", "options", "question.tracks", "question.submission_types"
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Show Answer",
        parameters=[
            build_expand_docs(
                "question", "options", "question.tracks", "question.submission_types"
            )
        ],
    ),
    create=extend_schema(summary="Create Answer"),
    update=extend_schema(
        summary="Update Answer",
        description="Please note that you cannot change an answer’s related objects (question, submission, review, person).",
    ),
    partial_update=extend_schema(
        summary="Update Answer (Partial Update)",
        description="Please note that you cannot change an answer’s related objects (question, submission, review, person).",
    ),
    destroy=extend_schema(summary="Delete Answer"),
)
class AnswerViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    queryset = Answer.objects.none()
    serializer_class = AnswerSerializer
    filterset_class = AnswerFilterSet
    search_fields = ("answer",)
    endpoint = "answers"
    permission_map = {
        "list": "submission.api_answer",
        "retrieve": "submission.api_answer",
        "create": "submission.api_answer",
        "update": "submission.api_answer",
        "partial_update": "submission.api_answer",
        "destroy": "submission.api_answer",
    }

    def get_queryset(self):
        queryset = (
            Answer.objects.filter(
                question__in=questions_for_user(self.event, self.request.user)
            )
            .select_related("question", "question__event")
            .order_by("pk")
        )
        question_fields = self.check_expanded_fields(
            "question.tracks", "question.submissions"
        )
        if question_fields or (
            prefetch_fields := self.check_expanded_fields("options")
        ):
            question_fields = [q.replace(".", "__") for q in question_fields]
            queryset = queryset.prefetch_related(*prefetch_fields, *question_fields)
        return queryset

    def get_unversioned_serializer_class(self):
        if self.action == "create":
            return AnswerCreateSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        # We don't want duplicate answers
        answer, _ = Answer.objects.update_or_create(
            question=serializer.validated_data["question"],
            review=serializer.validated_data.get("review"),
            submission=serializer.validated_data.get("submission"),
            person=serializer.validated_data.get("person"),
            defaults={"answer": serializer.validated_data["answer"]},
        )
        return answer
