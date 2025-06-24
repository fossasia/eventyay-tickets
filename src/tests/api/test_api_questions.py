import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.question import AnswerOptionSerializer, QuestionSerializer
from pretalx.api.versions import LEGACY
from pretalx.submission.models import AnswerOption, QuestionVariant


@pytest.mark.django_db
def test_question_serializer(answer):
    with scope(event=answer.question.event):
        data = QuestionSerializer(answer.question).data
    assert set(data.keys()) == {
        "id",
        "variant",
        "question",
        "question_required",
        "deadline",
        "freeze_after",
        "target",
        "options",
        "help_text",
        "default_answer",
        "min_length",
        "max_length",
        "submission_types",
        "tracks",
        "min_date",
        "max_date",
        "min_datetime",
        "max_datetime",
        "min_number",
        "max_number",
        "position",
    }


@pytest.mark.django_db
def test_answer_option_serializer(choice_question):
    with scope(event=choice_question.event):
        option = choice_question.options.first()
        data = AnswerOptionSerializer(option).data
        assert set(data.keys()) == {"id", "answer", "question", "position"}
        assert data["id"] == option.id
        assert data["answer"]["en"] == option.answer


@pytest.mark.django_db
@pytest.mark.parametrize("is_public", (True, False))
def test_questions_not_visible_by_default(client, question, schedule, is_public):
    with scope(event=question.event):
        question.is_public = is_public
        question.save()
    response = client.get(question.event.api_urls.questions, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert bool(len(content["results"])) is is_public


@pytest.mark.django_db
def test_public_questions_fewer_fields(client, question, schedule):
    with scope(event=question.event):
        question.is_public = True
        question.save()
    response = client.get(question.event.api_urls.questions, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["results"][0]["question"]["en"] == question.question
    assert "is_visible_to_reviewers" not in content["results"][0]


@pytest.mark.django_db
def test_organiser_can_see_question(client, orga_user_token, question):
    response = client.get(
        question.event.api_urls.questions,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert len(content["results"]) == 1
    assert content["results"][0]["id"] == question.id


@pytest.mark.django_db
@pytest.mark.parametrize("is_visible", (True, False))
def test_questions_not_visible_by_default_to_reviewers(
    client, review_user_token, question, is_visible
):
    with scope(event=question.event):
        question.is_visible_to_reviewers = is_visible
        question.save()
    response = client.get(
        question.event.api_urls.questions,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert bool(len(content["results"])) is is_visible


@pytest.mark.django_db
def test_organiser_can_create_question(event, orga_user_write_token, client):
    with scope(event=event):
        count = event.questions.all().count()
    response = client.post(
        event.api_urls.questions,
        data=json.dumps(
            {
                "question": "A question",
                "variant": "text",
                "target": "submission",
                "help_text": "hellllp",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        assert event.questions.all().count() == count + 1
        question = event.questions.all().first()
        assert question.question == "A question"
        assert question.variant == "text"
        assert question.target == "submission"
        assert question.help_text == "hellllp"
        assert (
            question.logged_actions()
            .filter(action_type="pretalx.question.create")
            .exists()
        )


@pytest.mark.django_db
def test_organiser_can_create_question_with_options(
    event, orga_user_write_token, client
):
    with scope(event=event):
        count = event.questions.all().count()
    response = client.post(
        event.api_urls.questions,
        data=json.dumps(
            {
                "question": "A choice question",
                "variant": "choices",
                "target": "submission",
                "options": [{"answer": "Option 1"}, {"answer": "Option 2"}],
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        assert event.questions.all().count() == count + 1
        question = event.questions.all().first()
        assert question.question == "A choice question"
        assert question.variant == "choices"
        assert question.options.count() == 2
        assert "Option 1" in [option.answer for option in question.options.all()]
        assert "Option 2" in [option.answer for option in question.options.all()]


@pytest.mark.django_db
def test_organiser_cannot_create_question_readonly_token(
    event, orga_user_token, client
):
    with scope(event=event):
        count = event.questions.all().count()
    response = client.post(
        event.api_urls.questions,
        data=json.dumps(
            {
                "question": "A question",
                "variant": "text",
                "target": "submission",
                "help_text": "hellllp",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403, response.text
    with scope(event=event):
        assert event.questions.all().count() == count
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.question.create")
            .exists()
        )


@pytest.mark.django_db
def test_organiser_can_edit_question(client, event, orga_user_write_token, question):
    response = client.patch(
        event.api_urls.questions + f"{question.pk}/",
        data=json.dumps(
            {
                "target": "speaker",
                "help_text": "hellllp",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200, response.text
    with scope(event=event):
        question.refresh_from_db()
        assert question.target == "speaker"
        assert question.help_text == "hellllp", response.text


@pytest.mark.django_db
def test_organiser_cannot_create_question_for_other_event(
    client, other_event, orga_user_token
):
    with scope(event=other_event):
        count = other_event.questions.all().count()
    response = client.post(
        other_event.api_urls.questions,
        data=json.dumps(
            {
                "question": "A question",
                "variant": "text",
                "target": "submission",
                "help_text": "hellllp",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=other_event):
        assert other_event.questions.all().count() == count


@pytest.mark.django_db
def test_reviewer_cannot_create_question(client, event, review_user_token):
    with scope(event=event):
        count = event.questions.all().count()
    response = client.post(
        event.api_urls.questions,
        data=json.dumps(
            {
                "question": "A question",
                "variant": "text",
                "target": "submission",
                "help_text": "hellllp",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text
    with scope(event=event):
        assert event.questions.all().count() == count


@pytest.mark.django_db
def test_reviewer_cannot_edit_question(client, event, review_user_token, question):
    response = client.patch(
        event.api_urls.questions + f"{question.pk}/",
        data=json.dumps(
            {
                "target": "speaker",
                "help_text": "hellllp",
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text
    with scope(event=event):
        question.refresh_from_db()
        assert question.target != "speaker"
        assert question.help_text != "hellllp"


@pytest.mark.django_db
@pytest.mark.parametrize("is_detail, method", ((False, "post"), (True, "put")))
def test_field_question_required(
    client, event, orga_user_write_token, question, is_detail, method
):
    url = event.api_urls.questions
    if is_detail:
        url += f"{question.pk}/"
    response = getattr(client, method)(
        url,
        data=json.dumps({}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.data.get("question")[0] == "This field is required."
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
def test_field_question_required_valid_choice(
    client, event, orga_user_write_token, question, is_detail, method
):
    url = event.api_urls.questions
    if is_detail:
        url += f"{question.pk}/"
    response = getattr(client, method)(
        url,
        data=json.dumps({"question_required": "invalid_choice"}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert (
        response.data.get("question_required")[0]
        == '"invalid_choice" is not a valid choice.'
    )
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
def test_field_contains_personal_data_valid_boolean(
    event, client, orga_user_write_token, question, is_detail, method
):
    url = event.api_urls.questions
    if is_detail:
        url += f"{question.pk}/"
    response = getattr(client, method)(
        url,
        data=json.dumps({"contains_personal_data": "not_an_boolean"}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.data.get("contains_personal_data")[0] == "Must be a valid boolean."
    assert response.status_code == 400, response.text


@pytest.mark.django_db
def test_organiser_can_delete_question(event, orga_user_write_token, client):
    with scope(event=event):
        question = event.questions.create(
            question="Delete me", variant="text", target="submission"
        )
        pk = question.pk
    response = client.delete(
        event.api_urls.questions + f"{pk}/",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 204, response.text
    with scope(event=event):
        assert not event.questions.filter(pk=pk).exists()
        assert (
            event.logged_actions()
            .filter(action_type="pretalx.question.delete")
            .exists()
        )


@pytest.mark.django_db
def test_organiser_cannot_delete_question_readonly_token(
    event, orga_user_token, client
):
    with scope(event=event):
        question = event.questions.create(
            question="Delete me", variant="text", target="submission"
        )
        pk = question.pk
    response = client.delete(
        event.api_urls.questions + f"{pk}/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403, response.text
    with scope(event=event):
        assert event.questions.filter(pk=pk).exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.question.delete")
            .exists()
        )


@pytest.mark.django_db
def test_organiser_cannot_delete_answered_question(
    event, orga_user_write_token, client, answer
):
    """Test that questions with answers cannot be deleted."""
    with scope(event=event):
        pk = answer.question.pk

    response = client.delete(
        event.api_urls.questions + f"{pk}/",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert "answers" in content[0].lower()

    with scope(event=event):
        assert event.questions.filter(pk=pk).exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.question.delete")
            .exists()
        )


@pytest.mark.django_db
def test_no_legacy_question_create(event, orga_user_write_token, client):
    response = client.post(
        event.api_urls.questions,
        data=json.dumps(
            {
                "question": "A question",
                "variant": "text",
                "target": "submission",
            }
        ),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_get_expanded_fields(
    event, orga_user_token, client, choice_question, track, submission_type
):
    with scope(event=event):
        choice_question.tracks.add(track)
        choice_question.submission_types.add(submission_type)
        option_name = choice_question.options.first().answer
        option_count = choice_question.options.all().count()

    response = client.get(
        event.api_urls.questions
        + f"{choice_question.pk}/?expand=options,tracks,submission_types",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)

    assert "options" in content
    assert len(content["options"]) == option_count
    assert option_name in [option["answer"]["en"] for option in content["options"]]
    assert "question" not in content["options"][0]
    assert content["tracks"][0]["name"]["en"] == track.name
    assert content["submission_types"][0]["name"]["en"] == submission_type.name


@pytest.mark.django_db
def test_bulk_get_questions(event, orga_user_token, client):
    with scope(event=event):
        event.questions.create(
            question="Question 1", variant="text", target="submission"
        )
        event.questions.create(question="Question 2", variant="text", target="speaker")

    response = client.get(
        event.api_urls.questions,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)

    assert content["count"] == 2
    questions = {q["question"]["en"] for q in content["results"]}
    assert "Question 1" in questions
    assert "Question 2" in questions


@pytest.mark.django_db
def test_filter_questions_by_target(event, orga_user_token, client):
    with scope(event=event):
        event.questions.create(
            question="Question 1", variant="text", target="submission"
        )
        event.questions.create(question="Question 2", variant="text", target="speaker")

    response = client.get(
        event.api_urls.questions + "?target=speaker",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)

    assert content["count"] == 1
    assert content["results"][0]["question"]["en"] == "Question 2"
    assert content["results"][0]["target"] == "speaker"


@pytest.mark.django_db
def test_filter_questions_by_variant(event, orga_user_token, client):
    with scope(event=event):
        event.questions.create(
            question="Question 1", variant="text", target="submission"
        )
        event.questions.create(
            question="Question 2", variant="boolean", target="submission"
        )

    response = client.get(
        event.api_urls.questions + "?variant=boolean",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)

    assert content["count"] == 1
    assert content["results"][0]["question"]["en"] == "Question 2"
    assert content["results"][0]["variant"] == "boolean"


@pytest.mark.django_db
def test_search_questions(event, orga_user_token, client):
    with scope(event=event):
        event.questions.create(
            question="Special question", variant="text", target="submission"
        )
        event.questions.create(
            question="Regular question", variant="text", target="submission"
        )

    response = client.get(
        event.api_urls.questions + "?q=special",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)

    assert content["count"] == 1
    assert content["results"][0]["question"]["en"] == "Special question"


@pytest.mark.django_db
def test_organiser_can_edit_question_options(
    event, orga_user_write_token, client, choice_question
):
    with scope(event=event):
        assert choice_question.options.count() == 3
        assert AnswerOption.objects.all().count() == choice_question.options.count()

    response = client.patch(
        event.api_urls.questions + f"{choice_question.pk}/",
        data=json.dumps(
            {"options": [{"answer": "Updated Option 1"}, {"answer": "New Option"}]}
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200, response.text

    with scope(event=event):
        choice_question.refresh_from_db()
        assert choice_question.options.count() == 2
        new_options = [o.answer for o in choice_question.options.all()]
        assert "Updated Option 1" in new_options
        assert "Original Option 1" not in new_options
        assert AnswerOption.objects.all().count() == 2


@pytest.mark.django_db
def test_cannot_create_question_with_track_from_other_event(
    event, other_event, orga_user_write_token, client
):
    with scope(event=other_event):
        track = other_event.tracks.create(name="Other Event Track")
        track_id = track.pk

    response = client.post(
        event.api_urls.questions,
        data=json.dumps(
            {
                "question": "Question with invalid track",
                "variant": "text",
                "target": "submission",
                "tracks": [track_id],
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )

    assert response.status_code == 400, response.text
    assert "tracks" in response.data
    assert str(track_id) in str(response.data["tracks"][0])

    with scope(event=event):
        assert not event.questions.all().exists()


@pytest.mark.django_db
def test_organiser_can_list_question_options(
    event, orga_user_token, client, choice_question
):
    with scope(event=event):
        option_count = choice_question.options.count()
        assert option_count > 0

    response = client.get(
        event.api_urls.question_options,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["count"] == option_count


@pytest.mark.django_db
def test_organiser_can_filter_question_options_by_question(
    event, orga_user_token, client, choice_question
):
    with scope(event=event):
        other_question = event.questions.create(
            question="Another choice question", variant=QuestionVariant.CHOICES
        )
        other_question.options.create(answer="Other Option")
        option_count = choice_question.options.count()
        assert option_count > 0
        assert (
            AnswerOption.objects.filter(question__event=event).count()
            == option_count + 1
        )

    response = client.get(
        event.api_urls.question_options + f"?question={choice_question.pk}",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["count"] == option_count
    assert all(opt["question"] == choice_question.pk for opt in content["results"])


@pytest.mark.django_db
def test_organiser_can_retrieve_question_option(
    event, orga_user_token, client, choice_question
):
    with scope(event=event):
        option = choice_question.options.first()
        option_id = option.pk
        option_answer = option.answer

    response = client.get(
        event.api_urls.question_options + f"{option_id}/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["id"] == option_id
    assert content["answer"]["en"] == option_answer


@pytest.mark.django_db
def test_organiser_can_create_question_option(
    event, orga_user_write_token, client, choice_question
):
    with scope(event=event):
        initial_count = choice_question.options.count()

    response = client.post(
        event.api_urls.question_options,
        data=json.dumps(
            {
                "question": choice_question.pk,
                "answer": {"en": "New API Option"},
                "position": initial_count + 1,
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201, response.text
    content = json.loads(response.text)
    assert content["answer"]["en"] == "New API Option"
    assert content["question"] == choice_question.pk

    with scope(event=event):
        choice_question.refresh_from_db()
        assert choice_question.options.count() == initial_count + 1
        assert choice_question.options.filter(
            answer__contains="New API Option"
        ).exists()


@pytest.mark.django_db
def test_organiser_cannot_create_option_for_wrong_question_type(
    event, orga_user_write_token, client, question
):
    with scope(event=event):
        initial_count = question.options.count()
        assert question.variant == QuestionVariant.NUMBER

    response = client.post(
        event.api_urls.question_options,
        data=json.dumps(
            {
                "question": question.pk,
                "answer": {"en": "Invalid Option"},
            }
        ),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400, response.text
    assert "question" in response.data
    assert "Invalid pk" in str(response.data["question"])

    with scope(event=event):
        question.refresh_from_db()
        assert question.options.count() == initial_count


@pytest.mark.django_db
def test_organiser_can_update_question_option(
    event, orga_user_write_token, client, choice_question
):
    with scope(event=event):
        option = choice_question.options.first()
        option_id = option.pk

    new_answer = "Updated via API"
    response = client.patch(
        event.api_urls.question_options + f"{option_id}/",
        data=json.dumps({"answer": {"en": new_answer}}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["answer"]["en"] == new_answer

    with scope(event=event):
        option.refresh_from_db()
        assert str(option.answer) == new_answer


@pytest.mark.django_db
def test_organiser_can_delete_question_option(
    event, orga_user_write_token, client, choice_question
):
    with scope(event=event):
        option = choice_question.options.last()
        option_id = option.pk
        initial_count = choice_question.options.count()
        assert initial_count > 0

    response = client.delete(
        event.api_urls.question_options + f"{option_id}/",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 204, response.text

    with scope(event=event):
        choice_question.refresh_from_db()
        assert choice_question.options.count() == initial_count - 1
        assert not choice_question.options.filter(pk=option_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("is_visible", (True, False))
def test_reviewer_cannot_access_question_options(
    event, review_user_token, client, choice_question, is_visible
):
    with scope(event=event):
        choice_question.is_visible_to_reviewers = is_visible
        choice_question.save()

    response = client.get(
        event.api_urls.question_options,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert bool(len(content["results"])) is is_visible


@pytest.mark.django_db
def test_anonymous_cannot_access_question_options(event, client, choice_question):
    with scope(event=event):
        event.is_public = False
        event.save()

    response = client.get(event.api_urls.question_options)
    assert response.status_code == 401


@pytest.mark.django_db
def test_anonymous_cannot_access_question_options_nonpublic_question(
    event, client, choice_question
):
    with scope(event=event):
        choice_question.is_public = False
        choice_question.save()

    response = client.get(event.api_urls.question_options)
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["count"] == 0


@pytest.mark.django_db
def test_anonymous_can_access_question_options_public(event, client, choice_question):
    with scope(event=event):
        choice_question.is_public = True
        choice_question.save()
        count = choice_question.options.all().count()

    response = client.get(event.api_urls.question_options)
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["count"] == count


@pytest.mark.django_db
def test_organiser_can_expand_question_option_fields(
    event, orga_user_token, client, choice_question, track
):
    with scope(event=event):
        option_count = choice_question.options.count()
        assert option_count > 0
        choice_question.tracks.add(track)

    response = client.get(
        event.api_urls.question_options + "?expand=question",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["count"] == option_count
    assert isinstance(content["results"][0]["question"], dict)
    assert content["results"][0]["question"]["id"] == choice_question.pk
    assert content["results"][0]["question"]["tracks"][0] == track.pk

    response = client.get(
        event.api_urls.question_options + "?expand=question,question.tracks",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["count"] == option_count
    question_data = content["results"][0]["question"]
    assert isinstance(question_data, dict)
    assert question_data["id"] == choice_question.pk
    assert "tracks" in question_data
    assert isinstance(question_data["tracks"], list)
    assert len(question_data["tracks"]) == 1
    assert question_data["tracks"][0]["id"] == track.pk
    assert question_data["tracks"][0]["name"]["en"] == track.name
