import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.submission import (
    SubmissionOrgaSerializer,
    SubmissionSerializer,
    SubmissionTypeSerializer,
    TagSerializer,
    TrackSerializer,
)
from pretalx.submission.models import SubmissionStates


@pytest.mark.django_db
def test_submission_serializer(slot):
    with scope(event=slot.submission.event):
        data = SubmissionSerializer(
            slot.submission, context={"event": slot.submission.event}
        ).data
        assert set(data.keys()) == {
            "code",
            "speakers",
            "title",
            "submission_type",
            "state",
            "abstract",
            "description",
            "duration",
            "slot_count",
            "do_not_record",
            "content_locale",
            "slots",
            "tags",
            "image",
            "track",
            "resources",
            "answers",
        }


@pytest.mark.django_db
def test_tag_serializer(tag):
    with scope(event=tag.event):
        data = TagSerializer(tag, context={"event": tag.event}).data
        assert set(data.keys()) == {
            "id",
            "tag",
            "description",
            "color",
            "is_public",
        }


@pytest.mark.django_db
def test_track_serializer(track):
    with scope(event=track.event):
        data = TrackSerializer(track, context={"event": track.event}).data
        assert set(data.keys()) == {
            "id",
            "name",
            "description",
            "color",
            "position",
            "requires_access_code",
        }


@pytest.mark.django_db
def test_submission_serializer_for_organiser(submission, orga_user, resource, tag):
    with scope(event=submission.event):
        submission.tags.add(tag)
        submission.favourite_count = 3
        data = SubmissionOrgaSerializer(submission).data
        assert set(data.keys()) == {
            "code",
            "speakers",
            "title",
            "submission_type",
            "state",
            "pending_state",
            "abstract",
            "description",
            "duration",
            "slot_count",
            "do_not_record",
            "is_featured",
            "content_locale",
            "image",
            "answers",
            "track",
            "notes",
            "internal_notes",
            "resources",
            "tags",
            "review_code",
            "mean_score",
            "median_score",
            "assigned_reviewers",
            "anonymised_data",
            "access_code",
            "invitation_token",
            "reviews",
            "is_anonymised",
            "slots",
        }
        assert isinstance(data["speakers"], list)
        assert data["tags"] == [tag.id]


@pytest.mark.django_db
def test_can_only_see_public_submissions(
    client, slot, accepted_submission, rejected_submission, submission
):
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.text)

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
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_all_submissions(
    client,
    orga_user_token,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    answer,
):
    response = client.get(
        submission.event.api_urls.submissions + "?questions=all",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200, content
    assert content["count"] == 4
    assert content["results"][0]["title"] == slot.submission.title
    assert len(
        [submission for submission in content["results"] if submission["answers"] == []]
    )
    assert len(
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
    client,
    orga_user_token,
    review_user,
    submission,
    answer,
    event,
    is_visible_to_reviewers,
    is_reviewer,
    length,
    review_user_token,
):
    token = review_user_token if is_reviewer else orga_user_token

    with scope(event=event):
        question = answer.question
        question.is_visible_to_reviewers = is_visible_to_reviewers
        question.save()

    response = client.get(
        submission.event.api_urls.submissions + "?expand=answers.question",
        follow=True,
        headers={"Authorization": f"Token {token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200, content
    assert content["count"] == 1
    assert content["results"][0]["title"] == submission.title
    assert len(content["results"][0]["answers"]) == length


@pytest.mark.django_db
def test_orga_can_see_all_submissions_even_nonpublic(
    client, orga_user_token, slot, accepted_submission, rejected_submission, submission
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = client.get(
        submission.event.api_urls.submissions,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 4
    assert content["results"][0]["title"] == slot.submission.title


@pytest.mark.django_db
def test_can_only_see_public_talks(
    event, client, slot, accepted_submission, rejected_submission, submission
):
    response = client.get(
        submission.event.api_urls.submissions + "?expand=speakers", follow=True
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == slot.submission.title
    with scope(event=event):
        speaker_user = slot.submission.speakers.first()
        assert content["results"][0]["speakers"][0]["name"] == speaker_user.name
        assert (
            content["results"][0]["speakers"][0]["biography"]
            == speaker_user.event_profile(event).biography
        )


@pytest.mark.django_db
def test_can_only_see_public_talks_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = client.get(submission.event.api_urls.submissions, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_all_talks_even_nonpublic(
    client, orga_user_token, slot, accepted_submission, rejected_submission, submission
):
    submission.event.feature_flags["show_schedule"] = False
    submission.event.save()
    response = client.get(
        submission.event.api_urls.submissions + "?state=rejected",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"] == slot.submission.title


@pytest.mark.django_db
def test_reviewer_cannot_see_submissions_in_anonymised_phase(
    client,
    orga_user_token,
    review_user_token,
    submission,
    event,
):
    with scope(event=event):
        submission.event.active_review_phase.can_see_speaker_names = False
        submission.event.active_review_phase.save()
        submission.anonymised_data = json.dumps({"description": "CENSORED!"})
        submission.save()
    response = client.get(
        submission.event.api_urls.submissions,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    content = content["results"][0]
    assert len(content["speakers"]) == 1
    assert content["description"] != "CENSORED!"
    assert content["abstract"] == submission.abstract

    response = client.get(
        submission.event.api_urls.submissions,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_cannot_see_tags(client, tag):
    response = client.get(tag.event.api_urls.tags, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_tags(client, orga_user_token, tag):
    response = client.get(
        tag.event.api_urls.tags,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["tag"] == tag.tag


@pytest.mark.django_db
def test_orga_can_see_single_tag(client, orga_user_token, tag):
    response = client.get(
        tag.event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["tag"] == tag.tag
    assert "is_public" in content
    assert isinstance(content["description"], dict)


@pytest.mark.django_db
def test_orga_can_see_single_tag_locale_override(client, orga_user_token, tag):
    response = client.get(
        tag.event.api_urls.tags + f"{tag.pk}/?lang=en",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["tag"] == tag.tag
    assert "is_public" in content
    assert isinstance(content["description"], str)


@pytest.mark.django_db
def test_orga_can_see_single_legacy_tag(client, orga_user_token, tag):
    from pretalx.api.versions import LEGACY

    response = client.get(
        tag.event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    content = json.loads(response.text)

    assert response.status_code == 200, response.text
    assert content["tag"] == tag.tag
    assert "is_public" not in content
    orga_user_token.refresh_from_db()
    assert orga_user_token.version == "LEGACY"

    response = client.get(
        tag.event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    content = json.loads(response.text)
    assert response.status_code == 200, response.text
    assert content["tag"] == tag.tag
    assert "is_public" not in content


@pytest.mark.django_db
def test_orga_can_create_tags(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.tags,
        follow=True,
        data={"tag": "newtesttag", "color": "#00ff00"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201
    with scope(event=event):
        tag = event.tags.get(tag="newtesttag")
        assert tag.logged_actions().filter(action_type="pretalx.tag.create").exists()


@pytest.mark.django_db
def test_orga_cannot_create_duplicate_tags(client, orga_user_write_token, event, tag):
    response = client.post(
        event.api_urls.tags,
        follow=True,
        data={"tag": tag.tag, "color": "#00ff00"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400
    with scope(event=event):
        assert event.tags.count() == 1


@pytest.mark.django_db
def test_orga_cannot_create_tags_readonly_token(client, orga_user_token, event):
    response = client.post(
        event.api_urls.tags,
        follow=True,
        data={"tag": "newtesttag"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.tags.filter(tag="newtesttag").exists()
        assert (
            not event.logged_actions().filter(action_type="pretalx.tag.create").exists()
        )


@pytest.mark.django_db
def test_orga_can_update_tags(client, orga_user_write_token, event, tag):
    assert tag.tag != "newtesttag"
    response = client.patch(
        event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        data=json.dumps({"tag": "newtesttag"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=tag.event):
        tag.refresh_from_db()
        assert tag.tag == "newtesttag"
        assert tag.logged_actions().filter(action_type="pretalx.tag.update").exists()


@pytest.mark.django_db
def test_orga_cannot_update_tags_readonly_token(client, orga_user_token, tag):
    response = client.patch(
        tag.event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        data=json.dumps({"tag": "newtesttag"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=tag.event):
        tag.refresh_from_db()
        assert tag.tag != "newtesttag"
        assert (
            not tag.logged_actions().filter(action_type="pretalx.tag.update").exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_tags(client, orga_user_write_token, event, tag):
    assert tag.tag != "newtesttag"
    response = client.delete(
        event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=tag.event):
        assert event.tags.all().count() == 0
        assert event.logged_actions().filter(action_type="pretalx.tag.delete").exists()


@pytest.mark.django_db
def test_orga_cannot_delete_tags_readonly_token(client, orga_user_token, tag):
    response = client.delete(
        tag.event.api_urls.tags + f"{tag.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=tag.event):
        assert tag.event.tags.all().count() == 1


@pytest.mark.django_db
def test_cannot_see_tracks(client, track):
    response = client.get(track.event.api_urls.tracks, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_can_see_tracks_public_event(client, track, slot):
    with scope(event=track.event):
        track.event.is_public = True
        track.event.save()
    response = client.get(track.event.api_urls.tracks, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["name"]["en"] == track.name


@pytest.mark.django_db
def test_orga_can_see_tracks(client, orga_user_token, track):
    response = client.get(
        track.event.api_urls.tracks,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["name"]["en"] == track.name


@pytest.mark.django_db
def test_orga_can_see_single_track(client, orga_user_token, track):
    response = client.get(
        track.event.api_urls.tracks + f"{track.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["name"]["en"] == track.name
    assert isinstance(content["name"], dict)


@pytest.mark.django_db
def test_orga_can_see_single_track_locale_override(client, orga_user_token, track):
    response = client.get(
        track.event.api_urls.tracks + f"{track.pk}/?lang=en",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert isinstance(content["name"], str)


@pytest.mark.django_db
def test_no_legacy_track_api(client, orga_user_token, track):
    from pretalx.api.versions import LEGACY

    response = client.get(
        track.event.api_urls.tracks + f"{track.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_orga_can_create_tracks(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.tracks,
        follow=True,
        data={"name": "newtesttrack", "color": "#334455"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201
    with scope(event=event):
        track = event.tracks.get(name="newtesttrack")
        assert (
            track.logged_actions().filter(action_type="pretalx.track.create").exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_tracks_readonly_token(client, orga_user_token, event):
    response = client.post(
        event.api_urls.tracks,
        follow=True,
        data={"name": "newtesttrack"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.tracks.filter(name="newtesttrack").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.track.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_tracks(client, orga_user_write_token, event, track):
    assert track.name != "newtesttrack"
    response = client.patch(
        event.api_urls.tracks + f"{track.pk}/",
        follow=True,
        data=json.dumps({"name": "newtesttrack"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=track.event):
        track.refresh_from_db()
        assert track.name == "newtesttrack"
        assert (
            track.logged_actions().filter(action_type="pretalx.track.update").exists()
        )


@pytest.mark.django_db
def test_orga_cannot_update_tracks_readonly_token(client, orga_user_token, track):
    response = client.patch(
        track.event.api_urls.tracks + f"{track.pk}/",
        follow=True,
        data=json.dumps({"name": "newtesttrack"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=track.event):
        track.refresh_from_db()
        assert track.name != "newtesttrack"
        assert (
            not track.logged_actions()
            .filter(action_type="pretalx.track.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_tracks(client, orga_user_write_token, event, track):
    response = client.delete(
        event.api_urls.tracks + f"{track.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=track.event):
        assert event.tracks.all().count() == 0
        assert (
            event.logged_actions().filter(action_type="pretalx.track.delete").exists()
        )


@pytest.mark.django_db
def test_orga_cannot_delete_tracks_readonly_token(client, orga_user_token, track):
    response = client.delete(
        track.event.api_urls.tracks + f"{track.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=track.event):
        assert track.event.tracks.all().count() == 1


@pytest.mark.django_db
def test_submission_type_serializer(submission_type):
    with scope(event=submission_type.event):
        data = SubmissionTypeSerializer(
            submission_type, context={"event": submission_type.event}
        ).data
        assert set(data.keys()) == {
            "id",
            "name",
            "default_duration",
            "deadline",
            "requires_access_code",
        }


@pytest.mark.django_db
def test_cannot_see_submission_types(client, submission_type):
    with scope(event=submission_type.event):
        submission_type.event.is_public = False
        submission_type.event.save()
    response = client.get(submission_type.event.api_urls.submission_types, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_can_see_submission_types_public_event(client, submission_type, slot):
    response = client.get(submission_type.event.api_urls.submission_types, follow=True)
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2
    assert content["results"][1]["name"]["en"] == submission_type.name


@pytest.mark.django_db
def test_orga_can_see_submission_types(client, orga_user_token, submission_type):
    response = client.get(
        submission_type.event.api_urls.submission_types,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2
    assert content["results"][1]["name"]["en"] == submission_type.name


@pytest.mark.django_db
def test_orga_can_see_single_submission_type(client, orga_user_token, submission_type):
    response = client.get(
        submission_type.event.api_urls.submission_types + f"{submission_type.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["name"]["en"] == submission_type.name
    assert isinstance(content["name"], dict)


@pytest.mark.django_db
def test_orga_can_see_single_submission_type_locale_override(
    client, orga_user_token, submission_type
):
    response = client.get(
        submission_type.event.api_urls.submission_types
        + f"{submission_type.pk}/?lang=en",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert isinstance(content["name"], str)


@pytest.mark.django_db
def test_no_legacy_submission_type_api(client, orga_user_token, submission_type):
    from pretalx.api.versions import LEGACY

    response = client.get(
        submission_type.event.api_urls.submission_types + f"{submission_type.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_orga_can_create_submission_types(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.submission_types,
        follow=True,
        data={"name": "newtesttype", "default_duration": 45},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201
    with scope(event=event):
        submission_type = event.submission_types.get(name="newtesttype")
        assert (
            submission_type.logged_actions()
            .filter(action_type="pretalx.submission_type.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_submission_types_readonly_token(
    client, orga_user_token, event
):
    response = client.post(
        event.api_urls.submission_types,
        follow=True,
        data={"name": "newtesttype"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.submission_types.filter(name="newtesttype").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.submission_type.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_submission_types(
    client, orga_user_write_token, event, submission_type
):
    assert submission_type.name != "newtesttype"
    response = client.patch(
        event.api_urls.submission_types + f"{submission_type.pk}/",
        follow=True,
        data=json.dumps({"name": "newtesttype"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=submission_type.event):
        submission_type.refresh_from_db()
        assert submission_type.name == "newtesttype"
        assert (
            submission_type.logged_actions()
            .filter(action_type="pretalx.submission_type.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_update_submission_types_readonly_token(
    client, orga_user_token, submission_type
):
    response = client.patch(
        submission_type.event.api_urls.submission_types + f"{submission_type.pk}/",
        follow=True,
        data=json.dumps({"name": "newtesttype"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=submission_type.event):
        submission_type.refresh_from_db()
        assert submission_type.name != "newtesttype"
        assert (
            not submission_type.logged_actions()
            .filter(action_type="pretalx.submission_type.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_submission_types(
    client, orga_user_write_token, event, submission_type
):
    response = client.delete(
        event.api_urls.submission_types + f"{submission_type.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=event):
        assert not event.submission_types.filter(pk=submission_type.pk).exists()
        assert (
            event.logged_actions()
            .filter(action_type="pretalx.submission_type.delete")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_create_submission(
    client, orga_user_write_token, event, submission_type
):
    response = client.post(
        event.api_urls.submissions,
        follow=True,
        data={
            "title": "New Submission",
            "submission_type": submission_type.pk,
            "abstract": "Abstract",
            "description": "Description",
            "duration": 30,
            "content_locale": "en",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    content = json.loads(response.text)
    with scope(event=event):
        submission = event.submissions.get(code=content["code"])
        assert submission.title == "New Submission"
        assert submission.state == SubmissionStates.SUBMITTED
        assert (
            submission.logged_actions()
            .filter(action_type="pretalx.submission.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_submission_readonly_token(
    client, orga_user_token, event, submission_type
):
    response = client.post(
        event.api_urls.submissions,
        follow=True,
        data={
            "title": "New Submission",
            "submission_type": submission_type.pk,
            "abstract": "Abstract",
            "description": "Description",
            "duration": 30,
            "content_locale": "en",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.submissions.filter(title="New Submission").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.submission.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_submission(client, orga_user_write_token, submission):
    assert submission.title != "Updated Submission"
    response = client.patch(
        submission.event.api_urls.submissions + f"{submission.code}/",
        follow=True,
        data=json.dumps({"title": "Updated Submission"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.title == "Updated Submission"
        assert (
            submission.logged_actions()
            .filter(action_type="pretalx.submission.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_submission(client, orga_user_write_token, submission):
    assert submission.title != "Updated Submission"
    response = client.delete(
        submission.event.api_urls.submissions + f"{submission.code}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == "deleted"


@pytest.mark.django_db
def test_orga_cannot_update_submission_readonly_token(
    client, orga_user_token, submission
):
    response = client.patch(
        submission.event.api_urls.submissions + f"{submission.code}/",
        follow=True,
        data=json.dumps({"title": "Updated Submission"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.title != "Updated Submission"
        assert (
            not submission.logged_actions()
            .filter(action_type="pretalx.submission.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_accept_submission(client, orga_user_write_token, submission):
    assert submission.state == SubmissionStates.SUBMITTED
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/accept/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200, response.text
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.ACCEPTED
        assert (
            submission.logged_actions()
            .filter(action_type="pretalx.submission.accept")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_accept_submission_readonly_token(
    client, orga_user_token, submission
):
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/accept/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.SUBMITTED
        assert (
            not submission.logged_actions()
            .filter(action_type="pretalx.submission.accept")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_reject_submission(client, orga_user_write_token, submission):
    assert submission.state == SubmissionStates.SUBMITTED
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/reject/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.REJECTED
        assert (
            submission.logged_actions()
            .filter(action_type="pretalx.submission.reject")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_reject_submission_readonly_token(
    client, orga_user_token, submission
):
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/reject/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.SUBMITTED
        assert (
            not submission.logged_actions()
            .filter(action_type="pretalx.submission.reject")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_confirm_submission(
    client, orga_user_write_token, accepted_submission
):
    assert accepted_submission.state == SubmissionStates.ACCEPTED
    response = client.post(
        accepted_submission.event.api_urls.submissions
        + f"{accepted_submission.code}/confirm/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200
    with scope(event=accepted_submission.event):
        accepted_submission.refresh_from_db()
        assert accepted_submission.state == SubmissionStates.CONFIRMED
        assert (
            accepted_submission.logged_actions()
            .filter(action_type="pretalx.submission.confirm")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_confirm_submission_readonly_token(
    client, orga_user_token, accepted_submission
):
    response = client.post(
        accepted_submission.event.api_urls.submissions
        + f"{accepted_submission.code}/confirm/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=accepted_submission.event):
        accepted_submission.refresh_from_db()
        assert accepted_submission.state == SubmissionStates.ACCEPTED
        assert (
            not accepted_submission.logged_actions()
            .filter(action_type="pretalx.submission.confirm")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_cancel_submission(client, orga_user_write_token, accepted_submission):
    assert accepted_submission.state == SubmissionStates.ACCEPTED
    response = client.post(
        accepted_submission.event.api_urls.submissions
        + f"{accepted_submission.code}/cancel/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200
    with scope(event=accepted_submission.event):
        accepted_submission.refresh_from_db()
        assert accepted_submission.state == SubmissionStates.CANCELED
        assert (
            accepted_submission.logged_actions()
            .filter(action_type="pretalx.submission.cancel")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_cancel_submission_readonly_token(
    client, orga_user_token, accepted_submission
):
    response = client.post(
        accepted_submission.event.api_urls.submissions
        + f"{accepted_submission.code}/cancel/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=accepted_submission.event):
        accepted_submission.refresh_from_db()
        assert accepted_submission.state == SubmissionStates.ACCEPTED
        assert (
            not accepted_submission.logged_actions()
            .filter(action_type="pretalx.submission.cancel")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_make_submitted_submission(
    client, orga_user_write_token, rejected_submission
):
    assert rejected_submission.state == SubmissionStates.REJECTED
    response = client.post(
        rejected_submission.event.api_urls.submissions
        + f"{rejected_submission.code}/make-submitted/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200
    with scope(event=rejected_submission.event):
        rejected_submission.refresh_from_db()
        assert rejected_submission.state == SubmissionStates.SUBMITTED
        assert (
            rejected_submission.logged_actions()
            .filter(action_type="pretalx.submission.make_submitted")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_make_submitted_submission_readonly_token(
    client, orga_user_token, rejected_submission
):
    response = client.post(
        rejected_submission.event.api_urls.submissions
        + f"{rejected_submission.code}/make-submitted/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=rejected_submission.event):
        rejected_submission.refresh_from_db()
        assert rejected_submission.state == SubmissionStates.REJECTED
        assert (
            not rejected_submission.logged_actions()
            .filter(action_type="pretalx.submission.make_submitted")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_add_speaker_to_submission(
    client, orga_user_write_token, submission, speaker
):
    with scope(event=submission.event):
        submission.speakers.remove(speaker)
        assert speaker not in submission.speakers.all()
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/add-speaker/",
        follow=True,
        data=json.dumps({"email": speaker.email}),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200, response.text
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert speaker in submission.speakers.all()
        assert (
            submission.logged_actions()
            .filter(action_type="pretalx.submission.speakers.add")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_add_speaker_to_submission_readonly_token(
    client, orga_user_token, submission, speaker
):
    with scope(event=submission.event):
        submission.speakers.remove(speaker)
        assert speaker not in submission.speakers.all()
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/add-speaker/",
        follow=True,
        data=json.dumps({"email": speaker.email}),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert speaker not in submission.speakers.all()
        assert (
            not submission.logged_actions()
            .filter(action_type="pretalx.submission.speakers.add")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_remove_speaker_from_submission(
    client, orga_user_write_token, submission, speaker
):
    with scope(event=submission.event):
        submission.speakers.add(speaker)
    assert speaker in submission.speakers.all()
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/remove-speaker/",
        follow=True,
        data=json.dumps({"user": speaker.code}),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 200, response.text
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert speaker not in submission.speakers.all()
        assert (
            submission.logged_actions()
            .filter(action_type="pretalx.submission.speakers.remove")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_remove_speaker_from_submission_readonly_token(
    client, orga_user_token, submission, speaker
):
    with scope(event=submission.event):
        submission.speakers.add(speaker)
    response = client.post(
        submission.event.api_urls.submissions + f"{submission.code}/remove-speaker/",
        follow=True,
        data=json.dumps({"user": speaker.code}),
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert speaker in submission.speakers.all()
        assert (
            not submission.logged_actions()
            .filter(action_type="pretalx.submission.speakers.remove")
            .exists()
        )


@pytest.mark.django_db
def test_public_submission_expandable_fields(
    client, event, slot, answer, track, speaker_answer
):
    with scope(event=slot.submission.event):
        slot.submission.event.is_public = True
        slot.submission.event.save()
        slot.submission.state = SubmissionStates.ACCEPTED
        slot.submission.track = track
        slot.submission.save()
        speaker_user = slot.submission.speakers.first()
        answer.submission = slot.submission
        answer.person = speaker_user
        answer.save()
        answer.question.is_public = True
        answer.question.target = "submission"
        answer.question.save()
        speaker_answer.question.is_public = True
        speaker_answer.question.save()

    expand_fields = [
        "track",
        "slots",
        "slots.room",
        "submission_type",
        "speakers",
        "speakers.user",
        "speakers.answers",
        "speakers.answers.question",
        "answers",
        "answers.question",
    ]
    expand_query = ",".join(expand_fields)
    response = client.get(
        slot.submission.event.api_urls.submissions + f"?expand={expand_query}",
        follow=True,
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    submission_data = content["results"][0]

    with scope(event=event):
        assert submission_data["track"]["name"]["en"] == slot.submission.track.name
        assert (
            submission_data["submission_type"]["name"]["en"]
            == slot.submission.submission_type.name
        )
        assert submission_data["speakers"][0]["name"] == speaker_user.name
        assert len(submission_data["speakers"][0]["answers"]) == 1
        assert (
            submission_data["speakers"][0]["answers"][0]["question"]["id"]
            == speaker_answer.question_id
        )
        assert "email" not in submission_data["speakers"]
        assert submission_data["answers"][0]["question"]["id"] == answer.question_id
        assert len(submission_data["answers"]) == 1
        assert len(submission_data["slots"]) == 1
        assert submission_data["slots"][0]["room"]["id"] == slot.room_id


@pytest.mark.django_db
def test_list_favourites_unauthenticated(client, event):
    response = client.get(event.api_urls.submissions + "favourites/", follow=True)
    assert response.status_code == 403


@pytest.mark.django_db
def test_list_favourites_schedule_not_public(event, speaker_client, slot, speaker):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()
        slot.submission.add_favourite(speaker)

    response = speaker_client.get(
        event.api_urls.submissions + "favourites/", follow=True
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_list_favourites_empty(event, speaker_client, slot):
    response = speaker_client.get(
        event.api_urls.submissions + "favourites/", follow=True
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content == []


@pytest.mark.django_db
def test_list_favourites_with_data(event, speaker_client, slot, speaker):
    with scope(event=event):
        slot.submission.add_favourite(speaker)

    response = speaker_client.get(
        event.api_urls.submissions + "favourites/", follow=True
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content == [slot.submission.code]


@pytest.mark.django_db
def test_add_favourite_unauthenticated(client, event, slot):
    url = event.api_urls.submissions + f"{slot.submission.code}/favourite/"
    response = client.post(url, follow=True)
    assert response.status_code == 403


@pytest.mark.django_db
def test_add_favourite_schedule_not_public(event, speaker_client, slot, speaker):
    event.feature_flags["show_schedule"] = False
    event.save()

    url = event.api_urls.submissions + f"{slot.submission.code}/favourite/"
    response = speaker_client.post(url, follow=True)
    assert response.status_code == 403
    with scope(event=event):
        assert not slot.submission.favourites.filter(user=speaker).exists()


@pytest.mark.django_db
def test_add_favourite_success(event, speaker_client, slot, speaker):
    url = event.api_urls.submissions + f"{slot.submission.code}/favourite/"
    response = speaker_client.post(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.favourites.filter(user=speaker).exists()


@pytest.mark.django_db
def test_add_favourite_nonexistent_submission(event, speaker_client, slot):
    url = event.api_urls.submissions + "NONEXISTENT/favourite/"
    response = speaker_client.post(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_remove_favourite_success(event, speaker_client, slot, speaker):

    with scope(event=event):
        slot.submission.add_favourite(speaker)
        assert slot.submission.favourites.filter(user=speaker).exists()

    url = event.api_urls.submissions + f"{slot.submission.code}/favourite/"
    response = speaker_client.delete(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert not slot.submission.favourites.filter(user=speaker).exists()


@pytest.mark.django_db
def test_remove_favourite_not_favourited(event, speaker_client, slot, speaker):
    with scope(event=event):
        slot.submission.remove_favourite(speaker)
        assert not slot.submission.favourites.filter(user=speaker).exists()

    url = event.api_urls.submissions + f"{slot.submission.code}/favourite/"
    response = speaker_client.delete(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert not slot.submission.favourites.filter(user=speaker).exists()
