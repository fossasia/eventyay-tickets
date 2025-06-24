import json

import pytest
from django_scopes import scopes_disabled

from pretalx.api.serializers.team import TeamSerializer


@pytest.fixture
def other_team(other_organiser):
    team = other_organiser.teams.create(
        name="Other Test Team", organiser=other_organiser, can_change_submissions=True
    )
    return team


@pytest.mark.django_db
def test_team_serializer(team):
    with scopes_disabled():
        data = TeamSerializer(team).data
        assert set(data.keys()) == {
            "id",
            "name",
            "can_create_events",
            "can_change_teams",
            "can_change_organiser_settings",
            "can_change_event_settings",
            "can_change_submissions",
            "is_reviewer",
            "all_events",
            "limit_events",
            "limit_tracks",
            "force_hide_speaker_names",
            "invites",
            "members",
        }
        assert data["name"] == team.name


@pytest.mark.django_db
def test_cannot_see_teams_unauthenticated(client, organiser):
    response = client.get(f"/api/organisers/{organiser.slug}/teams/", follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_teams(client, orga_user_token, organiser, team):
    response = client.get(
        f"/api/organisers/{organiser.slug}/teams/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] > 0
    assert team.name in [t["name"] for t in content["results"]]


@pytest.mark.django_db
def test_orga_can_see_single_team(client, orga_user_token, organiser, team):
    response = client.get(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["name"] == team.name


@pytest.mark.django_db
def test_orga_cannot_see_other_organiser_team(
    client, orga_user_token, organiser, other_team
):
    response = client.get(
        f"/api/organisers/{organiser.slug}/teams/{other_team.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_create_teams(client, orga_user_write_token, organiser):
    team_count = organiser.teams.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/",
        follow=True,
        data={
            "name": "New API Team",
            "can_change_submissions": True,
            "is_reviewer": False,
            "limit_events": [],
            "all_events": True,
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    with scopes_disabled():
        assert organiser.teams.count() == team_count + 1
        new_team = organiser.teams.get(name="New API Team")
        assert new_team.can_change_submissions is True
        assert new_team.is_reviewer is False
        assert new_team.all_events is True


@pytest.mark.django_db
def test_orga_cannot_create_team_without_events(
    client, orga_user_write_token, organiser
):
    team_count = organiser.teams.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/",
        follow=True,
        data={
            "name": "New API Team",
            "can_change_submissions": True,
            "is_reviewer": False,
            "limit_events": [],
            "all_events": False,
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    with scopes_disabled():
        assert organiser.teams.count() == team_count


@pytest.mark.django_db
def test_orga_cannot_create_team_without_permissions(
    client, orga_user_write_token, organiser
):
    team_count = organiser.teams.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/",
        follow=True,
        data={
            "name": "New API Team",
            "can_change_submissions": False,
            "is_reviewer": False,
            "limit_events": [],
            "all_events": True,
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    with scopes_disabled():
        assert organiser.teams.count() == team_count


@pytest.mark.django_db
def test_orga_cannot_create_teams_readonly_token(client, orga_user_token, organiser):
    team_count = organiser.teams.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/",
        follow=True,
        data={"name": "New API Team Fail", "can_change_submissions": True},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    assert organiser.teams.count() == team_count


@pytest.mark.django_db
def test_orga_can_update_teams(client, orga_user_write_token, organiser, team):
    response = client.patch(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/",
        follow=True,
        data=json.dumps({"name": "Updated Team Name", "is_reviewer": True}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    team.refresh_from_db()
    assert team.name == "Updated Team Name"
    assert team.is_reviewer is True


@pytest.mark.django_db
def test_orga_cannot_update_teams_remove_last_permission(
    client, orga_user_write_token, organiser, team
):
    response = client.patch(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/",
        follow=True,
        data=json.dumps(
            {
                "is_reviewer": False,
                "can_create_events": False,
                "can_change_teams": False,
                "can_change_organiser_settings": False,
                "can_change_event_settings": False,
                "can_change_submissions": False,
            }
        ),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400
    team.refresh_from_db()
    assert team.can_change_submissions


@pytest.mark.django_db
def test_orga_cannot_update_teams_readonly_token(
    client, orga_user_token, organiser, team
):
    original_name = team.name
    response = client.patch(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/",
        follow=True,
        data=json.dumps({"name": "Updated Team Name Fail"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    team.refresh_from_db()
    assert team.name == original_name


@pytest.mark.django_db
def test_orga_can_delete_teams(
    client, orga_user_write_token, organiser, team, orga_user
):
    with scopes_disabled():
        team_pk = team.pk
        team.pk = None
        team.all_events = True
        team.save()
        other_team = team.organiser.teams.get(pk=team.pk)
        other_team.members.add(orga_user)
    team_count = organiser.teams.count()
    response = client.delete(
        f"/api/organisers/{organiser.slug}/teams/{team_pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204, response.text
    assert organiser.teams.count() == team_count - 1
    assert not organiser.teams.filter(pk=team_pk).exists()


@pytest.mark.django_db
def test_orga_cannot_delete_last_team(client, orga_user_write_token, organiser, team):
    team_count = organiser.teams.count()
    response = client.delete(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    assert organiser.teams.count() == team_count
    assert organiser.teams.filter(pk=team.pk).exists()


@pytest.mark.django_db
def test_orga_cannot_delete_teams_readonly_token(
    client, orga_user_token, organiser, team
):
    team_count = organiser.teams.count()
    response = client.delete(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    assert organiser.teams.count() == team_count


@pytest.mark.django_db
def test_orga_can_expand_related_fields(
    client, orga_user_token, organiser, team, invitation, event, track
):
    team.limit_tracks.add(track)
    team.save()

    response = client.get(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/?expand=members,invites,limit_tracks",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["name"] == team.name
    assert len(content["members"]) == 1
    assert content["members"][0]["code"] == team.members.first().code
    assert len(content["invites"]) == 1
    assert content["invites"][0]["email"] == invitation.email
    assert len(content["limit_tracks"]) == 1
    assert content["limit_tracks"][0]["name"]["en"] == track.name


@pytest.mark.django_db
def test_orga_can_invite_member(client, orga_user_write_token, organiser, team):
    invite_count = team.invites.count()
    member_count = team.members.count()
    invite_email = "new.invite@example.com"
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/invite/",
        follow=True,
        data={"email": invite_email},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    content = json.loads(response.text)
    assert content["email"] == invite_email
    assert team.invites.count() == invite_count + 1
    assert team.members.count() == member_count
    assert team.invites.filter(email=invite_email).exists()


@pytest.mark.django_db
def test_orga_cannot_invite_existing_member(
    client, orga_user_write_token, organiser, team, orga_user
):
    invite_count = team.invites.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/invite/",
        follow=True,
        data={"email": orga_user.email},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    assert "already a member" in response.text
    assert team.invites.count() == invite_count


@pytest.mark.django_db
def test_orga_cannot_invite_already_invited(
    client, orga_user_write_token, organiser, team, invitation
):
    invite_count = team.invites.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/invite/",
        follow=True,
        data={"email": invitation.email},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    assert "already been invited" in response.text
    assert team.invites.count() == invite_count


@pytest.mark.django_db
def test_orga_cannot_invite_readonly_token(client, orga_user_token, organiser, team):
    invite_count = team.invites.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/invite/",
        follow=True,
        data={"email": "fail.invite@example.com"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    assert team.invites.count() == invite_count


@pytest.mark.django_db
def test_orga_can_delete_invite(
    client, orga_user_write_token, organiser, team, invitation
):
    invite_count = team.invites.count()
    response = client.delete(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/invites/{invitation.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scopes_disabled():
        assert team.invites.count() == invite_count - 1
        assert not team.invites.filter(pk=invitation.pk).exists()
        assert (
            team.logged_actions()
            .filter(action_type="pretalx.team.invite.orga.retract")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_delete_invite_readonly_token(
    client, orga_user_token, organiser, team, invitation
):
    invite_count = team.invites.count()
    response = client.delete(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/invites/{invitation.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    assert team.invites.count() == invite_count


@pytest.mark.django_db
def test_orga_can_remove_member(
    client, orga_user_write_token, organiser, team, orga_user, other_orga_user
):
    team.members.add(other_orga_user)
    team.save()

    member_count = team.members.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/remove_member/",
        follow=True,
        data={"user_code": orga_user.code},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204, response.text
    with scopes_disabled():
        team.refresh_from_db()
        assert team.members.count() == member_count - 1
        assert not team.members.filter(pk=orga_user.pk).exists()
        assert (
            team.logged_actions()
            .filter(action_type="pretalx.team.remove_member")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_remove_member_readonly_token(
    client, orga_user_token, organiser, team, orga_user
):
    member_count = team.members.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/remove_member/",
        follow=True,
        data={"user_code": orga_user.code},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    team.refresh_from_db()
    assert team.members.count() == member_count


@pytest.mark.django_db
def test_orga_cannot_remove_non_member(
    client, orga_user_write_token, organiser, team, other_orga_user
):
    with scopes_disabled():
        team.members.remove(other_orga_user)
        member_count = team.members.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/remove_member/",
        follow=True,
        data={"user_code": other_orga_user.code},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    assert "not a member" in response.text
    assert team.members.count() == member_count


@pytest.mark.django_db
def test_orga_cannot_remove_nonexistent_user(
    client, orga_user_write_token, organiser, team
):
    member_count = team.members.count()
    response = client.post(
        f"/api/organisers/{organiser.slug}/teams/{team.pk}/remove_member/",
        follow=True,
        data={"user_code": "NONEXISTENTCODE"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 400, response.text
    assert "not found" in response.text
    assert team.members.count() == member_count
