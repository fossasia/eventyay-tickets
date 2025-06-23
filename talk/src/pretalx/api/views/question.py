from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS

from pretalx.api.serializers.question import (
    AnswerSerializer,
    AnswerWriteSerializer,
    QuestionSerializer,
)
from pretalx.submission.models import Answer, Question


def get_questions_for_user(event, user, include_inactive=False):
    if include_inactive:
        base_queryset = event.questions(manager="all_objects").all()
    else:
        base_queryset = event.questions.all()
    if user.has_perm("orga.change_submissions", event):
        return base_queryset
    # Anybody else cannot see inactive questions at the moment
    base_queryset = base_queryset.filter(active=True)
    if user.has_perm("orga.view_submissions", event) and user.has_perm(
        "orga.view_speakers", event
    ):
        # This is a bit hacky: During anonymous review, reviewers can't use the API
        # to retrieve questions and answers. We can fix that with a bit of work,
        # but for now, it's an edge case. Leaving it as TODO.
        return base_queryset.filter(is_visible_to_reviewers=True)
    if user.has_perm("agenda.view_schedule", event):
        return base_queryset.filter(is_public=True)
    return event.questions.none()


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.none()
    serializer_class = QuestionSerializer
    write_permission_required = "orga.edit_question"
    filterset_fields = ("is_public", "is_visible_to_reviewers", "target", "variant")
    search_fields = ("question",)

    def get_queryset(self):
        return get_questions_for_user(
            self.request.event, self.request.user, include_inactive=True
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)


def model_for_event(model, lookup="event"):
    return lambda request: model.objects.all().filter(**{lookup: request.event})


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


class AnswerViewSet(viewsets.ModelViewSet):
    queryset = Answer.objects.none()
    serializer_class = AnswerSerializer
    write_permission_required = "orga.change_submissions"
    filterset_class = AnswerFilterSet
    search_fields = ("answer",)

    def get_queryset(self):
        return (
            Answer.objects.filter(
                question_id__in=get_questions_for_user(
                    self.request.event, self.request.user
                ).values_list("id", flat=True)
            )
            .prefetch_related("options")
            .select_related("question", "person", "review", "submission")
        )

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return self.serializer_class
        return AnswerWriteSerializer

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
