import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.submission import (
    SubmissionOrgaSerializer,
    SubmissionSerializer,
    TagSerializer,
)


@pytest.mark.django_db
def test_submission_slot_serializer(slot):
    with scope(event=slot.submission.event):
        data = SubmissionSerializer(
            slot.submission, context={"event": slot.submission.event}
        ).data
        assert set(data.keys()) == {
            "code",
            "speakers",
            "title",
            "submission_type",
            "submission_type_id",
            "state",
            "abstract",
            "description",
            "duration",
            "slot_count",
            "do_not_record",
            "is_featured",
            "content_locale",
            "slot",
            "image",
            "track",
            "track_id",
            "resources",
            "answers",
        }
        assert set(data["slot"].keys()) == {"start", "end", "room", "room_id"}
        assert data["slot"]["room"] == slot.room.name


@pytest.mark.django_db
def test_tag_serializer(tag):
    with scope(event=tag.event):
        data = TagSerializer(tag, context={"event": tag.event}).data
        assert set(data.keys()) == {
            "id",
            "tag",
            "description",
            "color",
        }


@pytest.mark.django_db
def test_submission_serializer_for_organiser(submission, orga_user, resource, tag):
    with scope(event=submission.event):
        submission.tags.add(tag)
        submission.favourite_count = 3
        data = SubmissionOrgaSerializer(
            submission,
            event=submission.event,
            can_view_speakers=True,
        ).data
        assert set(data.keys()) == {
            "code",
            "speakers",
            "title",
            "submission_type",
            "submission_type_id",
            "state",
            "pending_state",
            "abstract",
            "description",
            "duration",
            "slot_count",
            "do_not_record",
            "is_featured",
            "content_locale",
            "slot",
            "image",
            "answers",
            "track",
            "track_id",
            "notes",
            "internal_notes",
            "created",
            "resources",
            "tags",
            "tag_ids",
            "favourite_count",
        }
        assert isinstance(data["speakers"], list)
        assert data["speakers"][0] == {
            "name": submission.speakers.first().name,
            "code": submission.speakers.first().code,
            "email": submission.speakers.first().email,
            "biography": submission.speakers.first()
            .event_profile(submission.event)
            .biography,
            "avatar": None,
            "avatar_source": None,
            "avatar_license": None,
        }
        assert data["tags"] == [tag.tag]
        assert data["tag_ids"] == [tag.id]
        assert data["submission_type"] == str(submission.submission_type.name)
        assert data["slot"] is None
        assert (
            data["created"]
            == submission.created.astimezone(submission.event.tz).isoformat()
        )
        assert data["resources"] == [
            {
                "resource": "http://testserver" + resource.resource.url,
                "description": resource.description,
            }
        ]


@pytest.mark.django_db
def test_submission_serializer(submission, resource):
    with scope(event=submission.event):
        data = SubmissionSerializer(
            submission, context={"event": submission.event}
        ).data
        assert set(data.keys()) == {
            "code",
            "speakers",
            "title",
            "submission_type",
            "submission_type_id",
            "state",
            "abstract",
            "description",
            "duration",
            "slot_count",
            "do_not_record",
            "is_featured",
            "content_locale",
            "slot",
            "image",
            "track",
            "track_id",
            "resources",
            "answers",
        }
        assert isinstance(data["speakers"], list)
        assert data["speakers"] == []
        assert data["submission_type"] == str(submission.submission_type.name)
        assert data["slot"] is None
        assert data["resources"] == [
            {
                "resource": "http://testserver" + resource.resource.url,
                "description": resource.description,
            }
        ]


@pytest.mark.django_db
def test_can_only_see_public_submissions(
    client, slot, accepted_submission, rejected_submission, submission
):
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == slot.submission.title


@pytest.mark.django_db
def test_can_only_see_public_submissions_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission, answer
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 0
    assert all(submission["answers"] == [] for submission in content["results"])


@pytest.mark.django_db
def test_orga_can_see_all_submissions(
    orga_client, slot, accepted_submission, rejected_submission, submission, answer
):
    response = orga_client.get(
        submission.event.api_urls.submissions + "?questions=all", follow=True
    )
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 4
    assert content["results"][0]["title"] == slot.submission.title
    assert len(
        [submission for submission in content["results"] if submission["answers"] == []]
    )
    assert len(
        [submission for submission in content["results"] if submission["answers"] != []]
    )


@pytest.mark.django_db
def test_orga_can_see_all_submissions_wrong_question(
    orga_client, slot, accepted_submission, rejected_submission, submission, answer
):
    response = orga_client.get(
        submission.event.api_urls.submissions + "?questions=1212112", follow=True
    )
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 4
    assert content["results"][0]["title"] == slot.submission.title
    assert not len(
        [submission for submission in content["results"] if submission["answers"] != []]
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_visible_to_reviewers,is_reviewer,length",
    (
        (True, True, 1),
        (False, True, 0),
        (True, False, 1),
        (False, False, 1),
    ),
)
def test_answer_is_visible_to_reviewers(
    orga_client,
    review_user,
    submission,
    answer,
    event,
    is_visible_to_reviewers,
    is_reviewer,
    length,
):
    if is_reviewer:
        orga_client.force_login(review_user)

    with scope(event=event):
        question = answer.question
        question.is_visible_to_reviewers = is_visible_to_reviewers
        question.save()

    response = orga_client.get(
        submission.event.api_urls.submissions + f"?questions={answer.question_id}",
        follow=True,
    )
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == submission.title
    assert len(content["results"][0]["answers"]) == length


@pytest.mark.django_db
def test_orga_can_see_all_submissions_even_nonpublic(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 4
    assert content["results"][0]["title"] == slot.submission.title


@pytest.mark.django_db
def test_only_see_talks_when_a_release_exists(
    orga_client, confirmed_submission, rejected_submission, submission
):
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert content["count"] == 0


@pytest.mark.django_db
def test_can_only_see_public_talks(
    event, client, slot, accepted_submission, rejected_submission, submission
):
    response = client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == slot.submission.title
    with scope(event=event):
        speaker = slot.submission.speakers.first()
        assert content["results"][0]["speakers"][0]["name"] == speaker.name
        assert (
            content["results"][0]["speakers"][0]["biography"]
            == speaker.event_profile(event).biography
        )


@pytest.mark.django_db
def test_can_only_see_public_talks_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 0


@pytest.mark.django_db
def test_orga_can_see_all_talks(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == slot.submission.title


@pytest.mark.django_db
def test_orga_can_see_all_talks_even_nonpublic(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == slot.submission.title


@pytest.mark.django_db
def test_reviewer_cannot_see_speakers_and_anonymised_content(
    orga_client,
    review_user,
    submission,
    event,
):
    with scope(event=event):
        submission.event.active_review_phase.can_see_speaker_names = False
        submission.event.active_review_phase.save()
        submission.anonymised_data = json.dumps({"description": "CENSORED!"})
        submission.save()
    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    assert response.status_code == 200
    content = json.loads(response.content.decode())
    content = content["results"][0]
    assert len(content["speakers"]) == 1
    assert content["description"] != "CENSORED!"
    assert content["abstract"] == submission.abstract

    orga_client.force_login(review_user)

    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    assert response.status_code == 200
    content = json.loads(response.content.decode())
    content = content["results"][0]
    assert content["speakers"] == []
    assert content["description"] == "CENSORED!"
    assert content["abstract"] == submission.abstract


@pytest.mark.django_db
def test_cannot_see_tags(client, tag):
    response = client.get(tag.event.api_urls.tags, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 0


@pytest.mark.django_db
def test_orga_can_see_tags(orga_client, tag):
    response = orga_client.get(tag.event.api_urls.tags, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["tag"] == tag.tag


@pytest.mark.django_db
def test_orga_can_see_single_tag(orga_client, tag):
    response = orga_client.get(tag.event.api_urls.tags + f"{tag.tag}/", follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content["tag"] == tag.tag
