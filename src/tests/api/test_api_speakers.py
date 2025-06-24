import json

import pytest
from django_scopes import scope

from pretalx.person.models import SpeakerProfile, UserApiToken
from pretalx.submission.models import Answer, Question, QuestionTarget, Submission


@pytest.fixture
def personal_answer(event, speaker):
    with scope(event=event):
        question = Question.objects.create(
            event=event,
            question="Personal question?",
            target=QuestionTarget.SPEAKER,
            active=True,
        )
        return Answer.objects.create(
            answer="foo",
            question=question,
            person=speaker,
        )


@pytest.mark.django_db
def test_speaker_list_anonymous_nopublic(client, event, speaker):
    event.feature_flags["show_schedule"] = False
    event.save()
    response = client.get(event.api_urls.speakers, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_speaker_list_anonymous_public(
    client, event, slot, speaker, accepted_submission, rejected_submission
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        submission = slot.submission

    response = client.get(event.api_urls.speakers, follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)

    assert content["count"] == 1
    assert len(content["results"]) == 1
    result = content["results"][0]
    assert result["code"] == speaker.code
    assert result["name"] == speaker.name
    assert result["biography"] == profile.biography
    assert accepted_submission.code not in result["submissions"]
    assert rejected_submission.code not in result["submissions"]
    assert submission.code in result["submissions"]
    assert "avatar_url" in result
    assert "answers" in result
    assert "email" not in result
    assert "avatar" not in result


@pytest.mark.django_db
def test_speaker_list_reviewer_nopublic_names_hidden(
    client, review_user_token, event, slot, accepted_submission, rejected_submission
):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()
        event.save()
    response = client.get(
        event.api_urls.speakers,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_speaker_list_reviewer_public_names_hidden(
    client, review_user_token, event, slot, accepted_submission, rejected_submission
):
    with scope(event=event):
        event.feature_flags["show_schedule"] = True
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()
        event.save()

    response = client.get(
        event.api_urls.speakers,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_speaker_list_reviewer_nopublic_names_visible(
    client,
    review_user_token,
    event,
    speaker,
    accepted_submission,
    rejected_submission,
):
    with scope(event=event):
        event.active_review_phase.can_see_speaker_names = True
        event.active_review_phase.save()

    with scope(event=event):
        speakers = {
            sub.speakers.first().code
            for sub in [accepted_submission, rejected_submission]
        }

    response = client.get(
        event.api_urls.speakers,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 2
    assert {res["code"] for res in content["results"]} == speakers


@pytest.mark.django_db
def test_speaker_list_orga_nopublic(
    client,
    orga_user_token,
    event,
    speaker,
    other_speaker,
    accepted_submission,
    rejected_submission,
):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()

    response = client.get(
        event.api_urls.speakers,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 2
    assert {res["code"] for res in content["results"]} == {
        speaker.code,
        other_speaker.code,
    }

    result = next(res for res in content["results"] if res["code"] == speaker.code)
    assert "email" in result
    assert "has_arrived" in result
    assert "availabilities" not in result


@pytest.mark.django_db
def test_speaker_list_orga_pagination_limit_offset(
    client, orga_user_token, event, accepted_submission, rejected_submission
):
    response = client.get(
        event.api_urls.speakers + "?limit=1&offset=0",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 2
    assert len(content["results"]) == 1
    assert "offset=1" in content["next"]


@pytest.mark.django_db
def test_speaker_list_orga_pagination_page_number(
    client, orga_user_token, event, accepted_submission, rejected_submission
):
    response = client.get(
        event.api_urls.speakers + "?page_size=1",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 2
    assert len(content["results"]) == 1
    assert "page=2" in content["next"]


@pytest.mark.django_db
def test_speaker_list_search_by_name(
    client, event, speaker, slot, other_slot, other_speaker
):
    with scope(event=event):
        other_slot.submission.speakers.add(other_speaker)
    name_to_find = speaker.name
    response = client.get(
        event.api_urls.speakers + f"?q={name_to_find}",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 1
    assert any(res["name"] == name_to_find for res in content["results"])


@pytest.mark.django_db
def test_speaker_list_search_by_email_public(
    client, event, speaker, slot, other_slot, other_speaker
):
    with scope(event=event):
        other_slot.submission.speakers.add(other_speaker)
    email_to_find = speaker.email
    response = client.get(
        event.api_urls.speakers + f"?q={email_to_find}",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 0


@pytest.mark.django_db
def test_speaker_list_search_by_email_authenticated(
    client, orga_user_token, event, speaker, slot, other_slot, other_speaker
):
    with scope(event=event):
        other_slot.submission.speakers.add(other_speaker)
    email_to_find = speaker.email
    response = client.get(
        event.api_urls.speakers + f"?q={email_to_find}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["count"] == 1
    assert content["results"][0]["email"] == email_to_find


@pytest.mark.django_db
def test_speaker_list_expand_submissions(
    client, orga_user_token, event, accepted_submission, rejected_submission, speaker
):
    response = client.get(
        event.api_urls.speakers + "?expand=submissions",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    result = next(res for res in content["results"] if res["code"] == speaker.code)
    assert isinstance(result["submissions"], list)
    assert len(result["submissions"]) > 0
    assert "title" in result["submissions"][0]
    assert result["submissions"][0]["code"] == accepted_submission.code


@pytest.mark.django_db
def test_speaker_list_expand_answers(
    client,
    orga_user_token,
    event,
    accepted_submission,
    rejected_submission,
    speaker,
    other_speaker,
    personal_answer,
):
    with scope(event=event):
        Answer.objects.create(
            question=personal_answer.question, answer="foobarbar", person=other_speaker
        )
    response = client.get(
        event.api_urls.speakers + "?expand=answers,answers.question",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    result = next(res for res in content["results"] if res["code"] == speaker.code)
    assert isinstance(result["answers"], list)
    assert len(result["answers"]) == 1
    assert "question" in result["answers"][0]
    assert result["answers"][0]["id"] == personal_answer.pk
    assert result["answers"][0]["answer"] == personal_answer.answer
    assert result["answers"][0]["question"]["id"] == personal_answer.question.id


@pytest.mark.django_db
def test_speaker_list_expand_block_recursion(
    client,
    orga_user_token,
    event,
    accepted_submission,
    rejected_submission,
    speaker,
    other_speaker,
    personal_answer,
):
    with scope(event=event):
        Answer.objects.create(
            question=personal_answer.question, answer="foobarbar", person=other_speaker
        )
    response = client.get(
        event.api_urls.speakers
        + "?expand=answers,answers.question,answers.question.answers",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_speaker_list_multiple_talks_not_duplicated(client, event, slot, other_slot):
    with scope(event=event):
        submission = slot.submission
        speaker = submission.speakers.first()
        other_submission = other_slot.submission
        other_submission.speakers.set([speaker])
        other_submission.save()

    response = client.get(event.api_urls.speakers, follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)

    assert content["count"] == 1
    assert content["results"][0]["code"] == speaker.code
    assert set(content["results"][0]["submissions"]) == {
        submission.code,
        other_submission.code,
    }


@pytest.mark.django_db
def test_speaker_retrieve_anonymous_nopublic(client, event, speaker, slot):
    event.feature_flags["show_schedule"] = False
    event.save()
    response = client.get(event.api_urls.speakers + f"{speaker.code}/", follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_speaker_retrieve_anonymous_public(
    client, event, slot, accepted_submission, speaker
):
    with scope(event=event):
        speaker = accepted_submission.speakers.first()
        profile = speaker.event_profile(event)
        submission = slot.submission

    response = client.get(event.api_urls.speakers + f"{speaker.code}/", follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["code"] == speaker.code
    assert content["name"] == speaker.name
    assert content["biography"] == profile.biography
    assert accepted_submission.code not in content["submissions"]
    assert submission.code in content["submissions"]
    assert "email" not in content


@pytest.mark.django_db
def test_speaker_retrieve_orga(
    client, orga_user_token, event, speaker, accepted_submission
):
    response = client.get(
        event.api_urls.speakers + f"{speaker.code}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["code"] == speaker.code
    assert content["name"] == speaker.name
    assert "email" in content


@pytest.mark.django_db
def test_speaker_retrieve_expand_answers(
    client, orga_user_token, event, personal_answer, speaker, accepted_submission
):
    response = client.get(
        event.api_urls.speakers + f"{speaker.code}/?expand=answers",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert isinstance(content["answers"], list)
    assert len(content["answers"]) == 1
    assert "question" in content["answers"][0]
    assert content["answers"][0]["id"] == personal_answer.pk


@pytest.mark.django_db
@pytest.mark.parametrize("expand", (False, True))
@pytest.mark.parametrize(
    "is_visible_to_reviewers, is_reviewer, can_see",
    (
        (True, True, True),  # Visible question, reviewer -> can see
        (False, True, False),  # Hidden question, reviewer -> cannot see
        (True, False, True),  # Visible question, orga -> can see
        (False, False, True),  # Hidden question, orga -> can see
    ),
)
def test_speaker_answer_visibility(
    client,
    orga_user_token,
    review_user_token,
    event,
    speaker,
    slot,
    personal_answer,
    is_visible_to_reviewers,
    is_reviewer,
    can_see,
    expand,
):
    token = review_user_token if is_reviewer else orga_user_token
    with scope(event=event):
        question = personal_answer.question
        question.is_visible_to_reviewers = is_visible_to_reviewers
        question.save()

    expand = "?expand=answers" if expand else ""
    response = client.get(
        event.api_urls.speakers + f"{speaker.code}/{expand}",
        follow=True,
        headers={"Authorization": f"Token {token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)

    if can_see:
        assert len(content["answers"]) == 1
        if expand:
            assert content["answers"][0]["id"] == personal_answer.pk
        else:
            assert content["answers"][0] == personal_answer.pk
    else:
        assert len(content["answers"]) == 0


@pytest.mark.django_db
def test_speaker_update_by_orga(
    client, orga_user_write_token, event, speaker, submission
):
    new_bio = "An updated biography."
    response = client.patch(
        event.api_urls.speakers + f"{speaker.code}/",
        data=json.dumps({"biography": new_bio}),
        follow=True,
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["biography"] == new_bio

    with scope(event=event):
        profile = speaker.event_profile(event)
        assert profile.biography == new_bio
        assert (
            profile.logged_actions()
            .filter(action_type="pretalx.user.profile.update")
            .exists()
        )


@pytest.mark.django_db
def test_speaker_update_by_orga_readonly(
    client, orga_user_token, event, speaker, submission
):
    response = client.patch(
        event.api_urls.speakers + f"{speaker.code}/",
        data=json.dumps({"biography": "Readonly update attempt"}),
        follow=True,
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_speaker_update_by_reviewer(
    client, review_user_token, event, speaker, submission
):
    response = client.patch(
        event.api_urls.speakers + f"{speaker.code}/",
        data=json.dumps({"biography": "Reviewer update attempt"}),
        follow=True,
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_speaker_update_by_anonymous(client, event, speaker, slot):
    response = client.patch(
        event.api_urls.speakers + f"{speaker.code}/",
        data=json.dumps({"biography": "Anonymous update attempt"}),
        follow=True,
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_speaker_update_change_name_email(
    client, orga_user_write_token, event, speaker, submission
):
    with scope(event=event):
        profile = speaker.event_profile(event)
    new_name = "New Speaker Name"
    new_email = "new.speaker@example.com"
    response = client.patch(
        event.api_urls.speakers + f"{speaker.code}/",
        data=json.dumps({"name": new_name, "email": new_email}),
        follow=True,
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["name"] == new_name
    assert content["email"] == new_email

    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.name == new_name
        assert speaker.email == new_email
        assert (
            profile.logged_actions()
            .filter(action_type="pretalx.user.profile.update")
            .exists()
        )


@pytest.mark.django_db
def test_speaker_update_by_orga_duplicate_email(
    client, orga_user_write_token, event, speaker, other_speaker, submission
):
    response = client.patch(
        event.api_urls.speakers + f"{speaker.code}/",
        data=json.dumps({"email": other_speaker.email}),
        follow=True,
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400

    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.email != other_speaker.email


@pytest.mark.django_db
def test_speaker_retrieve_answers_scoped_to_event(
    client,
    orga_user_token,
    event,
    other_event,
    speaker,
    submission_data,
    speaker_answer,
    orga_user,
):
    with scope(event=other_event):
        sub2 = Submission(**submission_data)
        sub2.event = other_event
        sub2.save()
        sub2.speakers.add(speaker)
        sub2.save()
        SpeakerProfile.objects.create(user=speaker, event=other_event)
        question2 = Question.objects.create(
            event=other_event,
            question="Question for Event 2?",
            target=QuestionTarget.SPEAKER,
            active=True,
        )
        answer2 = Answer.objects.create(
            answer="Answer 2", question=question2, person=speaker
        )
        team = other_event.teams.first()
        team.members.add(orga_user)
        other_orga_user_token = UserApiToken.objects.create(
            name="testtoken", user=orga_user, endpoints=orga_user_token.endpoints
        )
        other_orga_user_token.events.add(other_event)

    response1 = client.get(
        event.api_urls.speakers + f"{speaker.code}/?expand=answers",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response1.status_code == 200
    content1 = json.loads(response1.text)
    assert len(content1["answers"]) == 1
    assert content1["answers"][0]["id"] == speaker_answer.pk

    response2 = client.get(
        other_event.api_urls.speakers + f"{speaker.code}/?expand=answers",
        follow=True,
        headers={"Authorization": f"Token {other_orga_user_token.token}"},
    )
    assert response2.status_code == 200
    content2 = json.loads(response2.text)
    assert len(content2["answers"]) == 1
    assert content2["answers"][0]["id"] == answer2.pk
    assert content2["answers"][0]["answer"] == "Answer 2"
