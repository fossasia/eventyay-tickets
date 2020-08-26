import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.question import (
    AnswerSerializer,
    MinimalQuestionSerializer,
    QuestionSerializer,
)


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
            "review",
            "options",
        }
        data = QuestionSerializer(answer.question).data
    assert set(data.keys()) == {
        "id",
        "variant",
        "question",
        "required",
        "target",
        "options",
        "help_text",
        "default_answer",
        "contains_personal_data",
        "min_length",
        "max_length",
        "is_public",
        "is_visible_to_reviewers",
    }


@pytest.mark.django_db
def test_minimal_question_serializer(answer):
    with scope(event=answer.question.event):
        data = MinimalQuestionSerializer(answer.question).data
    assert set(data.keys()) == {"id", "question"}


@pytest.mark.django_db
@pytest.mark.parametrize("is_public", (True, False))
def test_questions_not_visible_by_default(client, question, schedule, is_public):
    with scope(event=question.event):
        question.is_public = is_public
        question.save()
    response = client.get(question.event.api_urls.questions, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert bool(len(content["results"])) is is_public


@pytest.mark.django_db
def test_organizer_can_see_question(orga_client, question):
    response = orga_client.get(question.event.api_urls.questions, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content["results"]) == 1
    assert content["results"][0]["id"] == question.id


@pytest.mark.django_db
@pytest.mark.parametrize("is_visible", (True, False))
def test_questions_not_visible_by_default_to_reviewers(
    review_client, question, is_visible
):
    with scope(event=question.event):
        question.is_visible_to_reviewers = is_visible
        question.save()
    response = review_client.get(question.event.api_urls.questions, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert bool(len(content["results"])) is is_visible


@pytest.mark.django_db
def test_organizer_can_create_question(event, orga_client):
    with scope(event=event):
        count = event.questions.all().count()
    response = orga_client.post(
        event.api_urls.questions,
        {
            "question": "A question",
            "variant": "text",
            "target": "submission",
            "help_text": "hellllp",
        },
    )
    assert response.status_code == 201, response.content.decode()
    with scope(event=event):
        assert event.questions.all().count() == count + 1
        question = event.questions.all().first()
        assert question.question == "A question"


@pytest.mark.django_db
def test_organizer_can_edit_question(event, orga_client, question):
    response = orga_client.patch(
        event.api_urls.questions + f"{question.pk}/",
        {"target": "speaker", "help_text": "hellllp",},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content.decode()
    with scope(event=event):
        question.refresh_from_db()
        assert question.target == "speaker"
        assert question.help_text == "hellllp", response.content.decode()


@pytest.mark.django_db
def test_organizer_cannot_create_question_for_other_event(other_event, orga_client):
    with scope(event=other_event):
        count = other_event.questions.all().count()
    response = orga_client.post(
        other_event.api_urls.questions,
        {
            "question": "A question",
            "variant": "text",
            "target": "submission",
            "help_text": "hellllp",
        },
    )
    assert response.status_code == 403
    with scope(event=other_event):
        assert other_event.questions.all().count() == count


@pytest.mark.django_db
def test_reviewer_cannot_create_question(event, review_client):
    with scope(event=event):
        count = event.questions.all().count()
    response = review_client.post(
        event.api_urls.questions,
        {
            "question": "A question",
            "variant": "text",
            "target": "submission",
            "help_text": "hellllp",
        },
    )
    assert response.status_code == 403, response.content.decode()
    with scope(event=event):
        assert event.questions.all().count() == count


@pytest.mark.django_db
def test_reviewer_cannot_edit_question(event, review_client, question):
    response = review_client.patch(
        event.api_urls.questions + f"{question.pk}/",
        {"target": "speaker", "help_text": "hellllp",},
        content_type="application/json",
    )
    assert response.status_code == 403, response.content.decode()
    with scope(event=event):
        question.refresh_from_db()
        assert question.target != "speaker"
        assert question.help_text != "hellllp"
