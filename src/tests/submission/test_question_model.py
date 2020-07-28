import json
from itertools import repeat

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django_scopes import scope

from pretalx.submission.models import Answer, AnswerOption, Question


@pytest.mark.parametrize("target", ("submission", "speaker", "reviewer"))
@pytest.mark.django_db
def test_missing_answers_submission_question(submission, target, question):
    with scope(event=submission.event):
        assert question.missing_answers() == 1
        assert (
            question.missing_answers(filter_talks=submission.event.submissions.all())
            == 1
        )
        question.target = target
        question.save()
        if target == "submission":
            Answer.objects.create(
                answer="True", submission=submission, question=question
            )
        elif target == "speaker":
            Answer.objects.create(
                answer="True", person=submission.speakers.first(), question=question
            )
        assert question.missing_answers() == 0


@pytest.mark.django_db
def test_question_base_properties(submission, question):
    a = Answer.objects.create(answer="True", submission=submission, question=question)
    assert a.event == question.event
    assert str(a.question.question) in str(a.question)
    assert str(a.question.question) in str(a)


@pytest.mark.parametrize(
    "variant,answer,expected",
    (
        ("number", "1", "1"),
        ("string", "hm", "hm"),
        ("text", "", ""),
        ("boolean", "True", "Yes"),
        ("boolean", "False", "No"),
        ("boolean", "None", ""),
        ("file", "answer", ""),
        ("choices", "answer", ""),
        ("lol", "lol", None),
    ),
)
@pytest.mark.django_db
def test_answer_string_property(event, variant, answer, expected):
    with scope(event=event):
        question = Question.objects.create(question="?", variant=variant, event=event)
        answer = Answer.objects.create(question=question, answer=answer)
        assert answer.answer_string == expected
