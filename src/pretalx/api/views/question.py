from rest_framework import viewsets

from pretalx.api.serializers.question import AnswerSerializer, QuestionSerializer
from pretalx.submission.models import Answer, Question


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


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.none()
    serializer_class = QuestionSerializer
    write_permission_required = "orga.edit_question"
    filterset_fields = ("is_public", "is_visible_to_reviewers", "target", "variant")
    search_fields = ("question",)

    def get_queryset(self):
        return (
            get_questions_for_user(self.request.event, self.request.user)
            or self.request.event.questions.none()
        )

    def perform_create(self, serializer):
        serializer.save(event=self.request.event)

    def perform_update(self, serializer):
        serializer.save(event=self.request.event)
