from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS

from pretalx.api.serializers.question import (
    AnswerSerializer,
    AnswerWriteSerializer,
    QuestionSerializer,
)
from pretalx.submission.models import Answer, Question, Review


def get_questions_for_user(event, user):
    if user.has_perm("orga.change_submissions", event):
        return event.questions.all()
    if user.has_perm("orga.view_submissions", event) and user.has_perm(
        "orga.view_speakers", event
    ):
        # This is a bit hacky: During anonymous review, reviewers can't use the API
        # to retrieve questions and answers. We can fix that with a bit of work,
        # but for now, it's an edge case. Leaving it as TODO.
        return event.questions.filter(is_visible_to_reviewers=True)
    if user.has_perm("agenda.view_schedule", event):
        return event.questions.filter(is_public=True)
    return event.questions.none()


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.none()
    serializer_class = QuestionSerializer
    write_permission_required = "orga.edit_question"
    filterset_fields = ("is_public", "is_visible_to_reviewers", "target", "variant")
    search_fields = ("question",)

    def get_queryset(self):
        return get_questions_for_user(self.request.event, self.request.user)

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)


def model_for_event(model, lookup="event"):
    return lambda request: model.objects.all().filter(**{lookup: request.event})


class AnswerFilterSet(filters.FilterSet):
    question = filters.ModelChoiceFilter(
        field_name="question_id", queryset=model_for_event(Question)
    )
    submission = filters.CharFilter(
        field_name="submission__code", lookup_expr="iexact",
    )
    person = filters.CharFilter(field_name="person__code", lookup_expr="iexact",)
    review = filters.ModelChoiceFilter(
        field_name="review_id",
        queryset=model_for_event(Review, lookup="submission__event"),
    )

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
        return Answer.objects.filter(
            question__in=get_questions_for_user(self.request.event, self.request.user)
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
