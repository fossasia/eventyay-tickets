import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.speaker import (
    SpeakerOrgaSerializer,
    SpeakerSerializer,
    SubmitterSerializer,
)


@pytest.mark.django_db
def test_submitter_serializer(submission):
    user = submission.speakers.first()
    data = SubmitterSerializer(user, context={"event": submission.event}).data
    assert data.keys() == {"name", "code", "biography", "avatar"}
    assert data["name"] == user.name
    assert data["code"] == user.code


@pytest.mark.django_db
def test_submitter_serializer_without_profile(submission):
    with scope(event=submission.event):
        user = submission.speakers.first()
        user.profiles.all().delete()
        data = SubmitterSerializer(user, context={"event": submission.event}).data
    assert data.keys() == {"name", "code", "biography", "avatar"}
    assert data["name"] == user.name
    assert data["code"] == user.code
    assert data["biography"] == ""


@pytest.mark.django_db
def test_speaker_serializer(slot):
    with scope(event=slot.submission.event):
        user_profile = slot.submission.speakers.first().profiles.first()
        user = user_profile.user
        data = SpeakerSerializer(user_profile).data
        assert slot.submission.code in data["submissions"]
    assert data.keys() == {"name", "code", "biography", "submissions", "avatar"}
    assert data["name"] == user.name
    assert data["code"] == user.code


@pytest.mark.django_db
def test_speaker_orga_serializer(slot):
    with scope(event=slot.submission.event):
        user_profile = slot.submission.speakers.first().profiles.first()
        user = user_profile.user
        data = SpeakerOrgaSerializer(user_profile).data
    assert data.keys() == {
        "name",
        "code",
        "biography",
        "submissions",
        "avatar",
        "answers",
        "email",
        "availabilities",
    }
    assert data["name"] == user.name
    assert data["code"] == user.code
    assert data["email"] == user.email
    assert slot.submission.code in data["submissions"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_visible_to_reviewers,is_reviewer,length",
    ((True, True, 1), (False, True, 0), (True, False, 1), (False, False, 1),),
)
def test_speaker_answer_is_visible_to_reviewers(
    orga_client,
    review_user,
    submission,
    speaker,
    personal_answer,
    event,
    is_visible_to_reviewers,
    is_reviewer,
    length,
):
    if is_reviewer:
        orga_client.force_login(review_user)

    with scope(event=event):
        question = personal_answer.question
        question.is_visible_to_reviewers = is_visible_to_reviewers
        question.save()

    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["name"] == speaker.name
    assert len(content["results"][0]["answers"]) == length


@pytest.mark.django_db
def test_can_only_see_public_speakers(
    client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
    event,
):
    response = client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    with scope(event=event):
        speaker = accepted_submission.speakers.first()
        assert content["results"][0]["name"] == speaker.name
        assert (
            content["results"][0]["biography"] == speaker.event_profile(event).biography
        )
    assert set(content["results"][0].keys()) == {
        "name",
        "code",
        "biography",
        "submissions",
        "avatar",
    }


@pytest.mark.django_db
def test_can_only_see_public_speakerss_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set("show_schedule", False)
    response = client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 0


@pytest.mark.django_db
def test_orga_can_see_all_speakers(
    orga_client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
):
    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 2
    assert set(content["results"][0].keys()) == {
        "name",
        "code",
        "email",
        "biography",
        "submissions",
        "answers",
        "avatar",
        "availabilities",
    }
    assert set(content["results"][0]["answers"][0].keys()) == {
        "answer",
        "answer_file",
        "person",
        "question",
        "submission",
        "options",
        "id",
    }


@pytest.mark.django_db
def test_orga_can_see_all_speakers_with_limit_and_offset(
    orga_client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
):
    response = orga_client.get(
        submission.event.api_urls.speakers + "?limit=1", follow=True
    )
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 2
    assert "offset=1" in content["next"]


@pytest.mark.django_db
def test_reviewer_cannot_see_speakers(
    review_client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
    event,
):
    with scope(event=event):
        submission.event.active_review_phase.can_see_speaker_names = False
        submission.event.active_review_phase.save()
    response = review_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert (
        content["count"] == 1
    )  # can see the slot's speaker, but not the other submissions'


@pytest.mark.django_db
def test_orga_can_see_all_speakers_even_nonpublic(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set("show_schedule", False)
    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 2


@pytest.mark.django_db
def test_orga_speakers_with_multiple_talks_are_not_duplicated(
    client, speaker, slot, other_slot, accepted_submission, other_accepted_submission
):
    other_accepted_submission.speakers.add(accepted_submission.speakers.first())
    response = client.get(accepted_submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 2
