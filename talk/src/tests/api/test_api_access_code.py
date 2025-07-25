import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.access_code import SubmitterAccessCodeSerializer


@pytest.mark.django_db
def test_access_code_serializer(submission_type, event, track):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode", track=track)
        data = SubmitterAccessCodeSerializer(
            access_code, context={"event": access_code.event}
        ).data
        assert set(data.keys()) == {
            "id",
            "code",
            "track",
            "submission_type",
            "valid_until",
            "maximum_uses",
            "redeemed",
        }
        assert data["track"] == track.pk


@pytest.mark.parametrize("is_public", (True, False))
@pytest.mark.django_db
def test_cannot_see_access_codes(client, event, is_public):
    with scope(event=event):
        event.is_public = is_public
        event.save()
    response = client.get(event.api_urls.access_codes, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_access_codes(client, orga_user_token, event):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")
    response = client.get(
        event.api_urls.access_codes,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] > 0
    assert access_code.code in [code["code"] for code in content["results"]]


@pytest.mark.django_db
def test_orga_can_see_single_access_code(client, orga_user_token, event):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")
    response = client.get(
        event.api_urls.access_codes + f"{access_code.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["code"] == access_code.code


@pytest.mark.django_db
def test_no_legacy_access_code_api(client, orga_user_token, event):
    from pretalx.api.versions import LEGACY

    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")
    response = client.get(
        event.api_urls.access_codes + f"{access_code.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_orga_can_create_access_codes(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.access_codes,
        follow=True,
        data={
            "code": "newtestaccesscode",
            "maximum_uses": 1,
            "foo": "bar",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        access_code = event.submitter_access_codes.get(code="newtestaccesscode")
        assert access_code.maximum_uses == 1
        assert (
            access_code.logged_actions()
            .filter(action_type="pretalx.access_code.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_access_codes_readonly_token(client, orga_user_token, event):
    response = client.post(
        event.api_urls.access_codes,
        follow=True,
        data={"code": "newtestaccesscode", "maximum_uses": 1},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.submitter_access_codes.filter(
            code="newtestaccesscode"
        ).exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.access_code.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_access_codes(client, orga_user_write_token, event):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")

    response = client.patch(
        event.api_urls.access_codes + f"{access_code.pk}/",
        follow=True,
        data=json.dumps({"code": "newtestcode"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        access_code.refresh_from_db()
        assert access_code.code == "newtestcode"
        assert (
            access_code.logged_actions()
            .filter(action_type="pretalx.access_code.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_update_access_codes_readonly_token(client, orga_user_token, event):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")

    response = client.patch(
        event.api_urls.access_codes + f"{access_code.pk}/",
        follow=True,
        data=json.dumps({"code": "newtestcode"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        access_code.refresh_from_db()
        assert access_code.code != "newtestcode"
        assert (
            not access_code.logged_actions()
            .filter(action_type="pretalx.access_code.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_access_codes(client, orga_user_write_token, event):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")

    response = client.delete(
        event.api_urls.access_codes + f"{access_code.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=event):
        assert not event.submitter_access_codes.filter(pk=access_code.pk).exists()
        assert (
            event.logged_actions()
            .filter(action_type="pretalx.access_code.delete")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_delete_access_codes_readonly_token(client, orga_user_token, event):
    with scope(event=event):
        access_code = event.submitter_access_codes.create(code="testcode")

    response = client.delete(
        event.api_urls.access_codes + f"{access_code.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=event):
        assert event.submitter_access_codes.filter(pk=access_code.pk).exists()


@pytest.mark.django_db
def test_orga_can_expand_related_fields(
    client, orga_user_token, event, submission_type
):
    with scope(event=event):
        track = event.tracks.create(name="Test Track")
        access_code = event.submitter_access_codes.create(
            code="expandcode", track=track, submission_type=submission_type
        )

    response = client.get(
        event.api_urls.access_codes + f"{access_code.pk}/?expand=track,submission_type",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["code"] == "expandcode"
    assert content["track"]["name"]["en"] == "Test Track"
    assert content["submission_type"]["name"]["en"] == submission_type.name


@pytest.mark.django_db
def test_orga_cannot_assign_track_from_other_event(
    client, orga_user_write_token, event, other_event
):
    with scope(event=other_event):
        other_track = other_event.tracks.create(name="Other Track")

    response = client.post(
        event.api_urls.access_codes,
        follow=True,
        data={
            "code": "newtestcode",
            "track": other_track.pk,
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )

    assert response.status_code == 400, response.text
    assert "track" in json.loads(response.text)

    with scope(event=event):
        assert not event.submitter_access_codes.filter(code="newtestcode").exists()
