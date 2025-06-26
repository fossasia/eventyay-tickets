import json

import pytest
from django.core.files.base import ContentFile
from django_scopes import scope

from pretalx.api.serializers.speaker_information import SpeakerInformationSerializer


@pytest.mark.django_db
def test_speaker_information_serializer(submission_type, event, track):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
        speaker_info.limit_tracks.add(track)
        speaker_info.limit_types.add(submission_type)

        data = SpeakerInformationSerializer(
            speaker_info, context={"event": speaker_info.event}
        ).data

        assert set(data.keys()) == {
            "id",
            "target_group",
            "title",
            "text",
            "resource",
            "limit_tracks",
            "limit_types",
        }
        assert data["target_group"] == "accepted"
        assert track.pk in data["limit_tracks"]
        assert submission_type.pk in data["limit_types"]


@pytest.mark.parametrize("is_public", (True, False))
@pytest.mark.django_db
def test_cannot_see_speaker_information(client, event, is_public):
    with scope(event=event):
        event.is_public = is_public
        event.save()
    response = client.get(event.api_urls.speaker_information, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_speaker_information(client, orga_user_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
    response = client.get(
        event.api_urls.speaker_information,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"]["en"] == speaker_info.title


@pytest.mark.django_db
def test_orga_can_see_single_speaker_information(client, orga_user_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
    response = client.get(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["title"]["en"] == speaker_info.title


@pytest.mark.django_db
def test_no_legacy_speaker_information_api(client, orga_user_token, event):
    from pretalx.api.versions import LEGACY

    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
        )
    response = client.get(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_orga_can_create_speaker_information(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "New Test Info",
            "text": "This is some new test information",
            "target_group": "accepted",
            "foo": "bar",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        speaker_info = event.information.all().first()
        assert speaker_info.title == "New Test Info"
        assert speaker_info.text == "This is some new test information"
        assert (
            speaker_info.logged_actions()
            .filter(action_type="pretalx.speaker_information.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_speaker_information_readonly_token(
    client, orga_user_token, event
):
    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "New Test Info",
            "text": "This is some new test information",
            "target_group": "accepted",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.information.filter(title="New Test Info").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.speaker_information.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_speaker_information(client, orga_user_write_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.patch(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        data=json.dumps({"title": "Updated Test Info"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Updated Test Info"
        assert (
            speaker_info.logged_actions()
            .filter(action_type="pretalx.speaker_information.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_update_speaker_information_readonly_token(
    client, orga_user_token, event
):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.patch(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        data=json.dumps({"title": "Updated Test Info"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title != "Updated Test Info"
        assert (
            not speaker_info.logged_actions()
            .filter(action_type="pretalx.speaker_information.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_speaker_information(client, orga_user_write_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.delete(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=event):
        assert not event.information.filter(pk=speaker_info.pk).exists()
        assert (
            event.logged_actions()
            .filter(action_type="pretalx.speaker_information.delete")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_delete_speaker_information_readonly_token(
    client, orga_user_token, event
):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.delete(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=event):
        assert event.information.filter(pk=speaker_info.pk).exists()


@pytest.mark.django_db
def test_orga_can_expand_related_fields(
    client, orga_user_token, event, submission_type
):
    with scope(event=event):
        track = event.tracks.create(name="Test Track")
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
        speaker_info.limit_tracks.add(track)
        speaker_info.limit_types.add(submission_type)

    response = client.get(
        event.api_urls.speaker_information
        + f"{speaker_info.pk}/?expand=limit_tracks,limit_types",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["title"]["en"] == "Test Info"
    assert content["limit_tracks"][0]["name"]["en"] == "Test Track"
    assert content["limit_types"][0]["name"]["en"] == submission_type.name


@pytest.mark.django_db
def test_orga_can_create_speaker_information_with_resource(
    client, orga_user_write_token, event
):
    response = client.post(
        "/api/upload/",
        data={"file": ContentFile("Test PDF content", name="test.pdf")},
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Disposition": 'attachment; filename="test.pdf"',
            "Content-Type": "application/pdf",
        },
    )
    assert response.status_code == 201, response.text
    file_id = response.data["id"]
    assert file_id.startswith("file:")

    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "Info with Resource",
            "text": "This information has an attached resource",
            "target_group": "accepted",
            "resource": file_id,
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text

    with scope(event=event):
        speaker_info = event.information.get(title="Info with Resource")
        assert speaker_info.resource is not None
        assert speaker_info.resource.name.endswith(".pdf")

        response = client.get(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            headers={
                "Authorization": f"Token {orga_user_write_token.token}",
            },
        )
        content = json.loads(response.text)
        assert response.status_code == 200
        assert content["resource"].startswith("http")
        assert content["resource"].endswith(".pdf")


@pytest.mark.django_db
def test_orga_cannot_assign_track_from_other_event(
    client, orga_user_write_token, event, other_event
):
    with scope(event=other_event):
        other_track = other_event.tracks.create(name="Other Track")

    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "New Test Info",
            "text": "This is some new test information",
            "target_group": "accepted",
            "limit_tracks": [other_track.pk],
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )

    assert response.status_code == 400, response.text
    assert "limit_tracks" in json.loads(response.text)

    with scope(event=event):
        assert not event.information.filter(title="New Test Info").exists()
