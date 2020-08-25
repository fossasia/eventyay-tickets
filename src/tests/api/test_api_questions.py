import pytest
from django_scopes import scope

from pretalx.api.serializers.question import AnswerSerializer, QuestionSerializer


@pytest.mark.django_db
def test_question_serializer(answer):
    with scope(event=answer.question.event):
        data = AnswerSerializer(answer).data
        assert set(data.keys()) == {
            "id",
            "question",
            "answer",
            "answer_file",
            "submission",
            "person",
            "options",
        }
        data = QuestionSerializer(answer.question).data
    assert set(data.keys()) == {"id", "question", "required", "target", "options"}
