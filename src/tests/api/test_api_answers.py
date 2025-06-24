import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.question import AnswerSerializer
from pretalx.submission.models import Answer


@pytest.mark.django_db
def test_answer_serializer(answer):
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
        assert data["id"] == answer.id
        assert data["question"] == answer.question_id
        assert data["submission"] == answer.submission.code


@pytest.mark.django_db
@pytest.mark.parametrize("is_public", (True, False))
def test_answers_not_visible_unauthenticated(client, answer, schedule, is_public):
    with scope(event=answer.event):
        answer.question.is_public = is_public
        answer.question.save()
    response = client.get(answer.event.api_urls.answers, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_organizer_can_see_answer(orga_user_token, client, answer):
    response = client.get(
        answer.event.api_urls.answers,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert len(content["results"]) == 1
    assert content["results"][0]["id"] == answer.id


@pytest.mark.django_db
@pytest.mark.parametrize("is_visible", (True, False))
def test_answers_not_visible_by_default_to_reviewers(
    client, review_user_token, answer, is_visible
):
    with scope(event=answer.event):
        answer.question.is_visible_to_reviewers = is_visible
        answer.question.save()
    response = client.get(
        answer.question.event.api_urls.answers,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_organizer_can_create_answer(
    event, orga_user_write_token, client, question, submission, speaker
):
    with scope(event=event):
        count = Answer.objects.filter(question__event=event).count()
    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.id,
                "submission": submission.code,
                "person": speaker.code,
                "answer": "Tralalalala",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        assert Answer.objects.filter(question__event=event).count() == count + 1
        answer = Answer.objects.filter(question__event=event).first()
        assert answer.answer == "Tralalalala"


@pytest.mark.parametrize("target", ("submission", "reviewer", "speaker"))
@pytest.mark.django_db
def test_organizer_cannot_create_answer_superflous_fields(
    event, orga_user_write_token, client, question, submission, speaker, review, target
):
    with scope(event=event):
        count = Answer.objects.filter(question__event=event).count()
        question.target = target
        question.save()
    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.id,
                "submission": submission.code,
                "person": speaker.code,
                "review": review.pk,
                "answer": "Tralalalala",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400, response.text
    with scope(event=event):
        assert Answer.objects.filter(question__event=event).count() == count


@pytest.mark.django_db
def test_duplicate_answer_updates_existing_answer(
    event, orga_user_write_token, client, question, submission, speaker, answer
):
    with scope(event=event):
        count = Answer.objects.filter(question__event=event).count()
        response = client.post(
            event.api_urls.answers,
            data=json.dumps(
                {
                    "question": answer.question_id,
                    "submission": answer.submission.code,
                    "person": "",
                    "answer": "Tralalalala",
                }
            ),
            content_type="application/json",
            headers={"Authorization": f"Token {orga_user_write_token.token}"},
        )
    assert response.status_code == 201, response.text
    with scope(event=event):
        assert Answer.objects.filter(question__event=event).count() == count
        answer = Answer.objects.filter(question__event=event).first()
        assert answer.answer == "Tralalalala"


@pytest.mark.django_db
def test_organizer_can_edit_answers(event, orga_user_write_token, client, answer):
    response = client.patch(
        event.api_urls.answers + f"{answer.pk}/",
        data=json.dumps({"answer": "ohno.png"}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200, response.text
    with scope(event=event):
        answer.refresh_from_db()
        assert answer.answer == "ohno.png"


@pytest.mark.django_db
def test_reviewer_cannot_create_answer(
    event, client, review_user_token, question, submission, speaker
):
    with scope(event=event):
        count = Answer.objects.filter(question__event=event).count()
    response = client.post(
        event.api_urls.answers,
        {
            "question": question.id,
            "submission": submission.code,
            "person": speaker.code,
            "answer": "Tralalalala",
        },
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text
    with scope(event=event):
        assert Answer.objects.filter(question__event=event).count() == count


@pytest.mark.django_db
def test_reviewer_cannot_edit_answer(event, client, review_user_token, answer):
    response = client.patch(
        event.api_urls.answers + f"{answer.pk}/",
        {"answer": "ohno.png"},
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text
    with scope(event=event):
        answer.refresh_from_db()
        assert answer.answer != "ohno.png"


@pytest.mark.django_db
@pytest.mark.parametrize("required_field", ("answer", "question"))
def test_fields_required_on_create(
    event, orga_user_write_token, client, required_field
):
    response = client.post(
        event.api_urls.answers,
        data=json.dumps({}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.data.get(required_field)[0] == "This field is required."
    assert response.status_code == 400, response.text


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_detail, method",
    (
        (False, "post"),
        (True, "put"),
        (True, "patch"),
    ),
)
def test_field_answer_may_not_be_blank(
    event, orga_user_write_token, client, answer, is_detail, method
):
    url = event.api_urls.answers
    if is_detail:
        url += f"{answer.pk}/"

    response = getattr(client, method)(
        url,
        data=json.dumps({"answer": ""}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.data.get("answer")[0] == "This field may not be blank."
    assert response.status_code == 400, response.text


@pytest.mark.django_db
def test_answer_validation_submission_question(
    event, orga_user_write_token, client, submission
):
    with scope(event=event):
        question = event.questions.create(
            question="Submission Question", variant="text", target="submission"
        )

    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": "Test answer",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "submission" in response.data

    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": "Test answer",
                "submission": submission.code,
                "review": 1,
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "review" in response.data


@pytest.mark.django_db
def test_answer_validation_reviewer_question(
    event, orga_user_write_token, client, review
):
    with scope(event=event):
        question = event.questions.create(
            question="Reviewer Question", variant="text", target="reviewer"
        )

    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": "Test answer",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "review" in response.data

    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": "Test answer",
                "review": review.pk,
                "submission": "abc123",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "submission" in response.data


@pytest.mark.django_db
def test_answer_validation_speaker_question(
    event, orga_user_write_token, client, speaker
):
    with scope(event=event):
        question = event.questions.create(
            question="Speaker Question", variant="text", target="speaker"
        )

    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": "Test answer",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "person" in response.data

    response = client.post(
        event.api_urls.answers,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": "Test answer",
                "person": speaker.code,
                "submission": "abc123",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "submission" in response.data
