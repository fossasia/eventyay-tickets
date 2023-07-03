import pytest
from django_scopes import scope, scopes_disabled

from pretalx.person.models.user import User, avatar_path
from pretalx.submission.models.question import Answer


@pytest.mark.parametrize(
    "email,expected",
    (
        ("one@two.com", "ac5be7f974137dc75bacee19b94fe0f8"),
        ("a_very_long.email@orga.org", "79bd022bbbd718d8e30f730169067b2a"),
    ),
)
def test_gravatar_parameter(email, expected):
    user = User(email=email)
    assert user.gravatar_parameter == expected


@pytest.mark.django_db
def test_user_deactivate(speaker, personal_answer, impersonal_answer, other_speaker):
    with scopes_disabled():
        assert Answer.objects.count() == 2
        count = speaker.own_actions().count()
        name = speaker.name
        email = speaker.email
        organiser = speaker.submissions.first().event.organiser
        team = organiser.teams.first()
        team.members.add(speaker)
        team.save()
        team_members = team.members.count()
        speaker.deactivate()
        speaker.refresh_from_db()
        assert speaker.own_actions().count() == count
        assert speaker.profiles.first().biography == ""
        assert speaker.name != name
        assert speaker.email != email
        assert Answer.objects.count() == 1
        assert Answer.objects.first().question.contains_personal_data is False
        assert team.members.count() == team_members - 1
        assert "deleted" in str(speaker).lower()
        assert speaker.get_permissions_for_event(Answer.objects.first().event) == set()


@pytest.mark.django_db
def test_administrator_permissions(event):
    user = User(email="one@two.com", is_administrator=True)
    permission_set = {
        "can_create_events",
        "can_change_teams",
        "can_change_organiser_settings",
        "can_change_event_settings",
        "can_change_submissions",
        "is_reviewer",
    }
    assert user.get_permissions_for_event("randomthing") == permission_set
    assert user.get_permissions_for_event(event) == permission_set
    assert list(user.get_events_for_permission(can_change_submissions=True)) == [event]
    assert event in user.get_events_with_any_permission()


@pytest.mark.django_db
def test_organizer_permissions(event, orga_user):
    assert list(orga_user.get_events_with_any_permission()) == [event]
    assert list(orga_user.get_events_for_permission(can_change_submissions=True)) == [
        event
    ]
    permission_set = {
        "can_create_events",
        "can_change_teams",
        "can_change_organiser_settings",
        "can_change_event_settings",
        "can_change_submissions",
    }
    assert orga_user.get_permissions_for_event(event) == permission_set


@pytest.mark.django_db
def test_do_not_shred_user_with_teams(orga_user):
    assert User.objects.count() == 1
    with pytest.raises(Exception):  # noqa
        orga_user.shred()
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_shred_user(user):
    assert User.objects.count() == 1
    user.shred()
    assert User.objects.count() == 0


def test_avatar_path():
    assert avatar_path(None, "foo").startswith("avatars/foo")


@pytest.mark.django_db
def test_unsaved_event_profile(event):
    with scope(event=event):
        assert not User(email="foo@example.com").event_profile(event).pk


@pytest.mark.django_db
def test_user_attributes(orga_user):
    assert not orga_user.has_avatar


@pytest.mark.django_db
def test_user_reset_password_without_text(orga_user, event):
    with scope(event=event):
        assert not orga_user.pw_reset_token
        orga_user.reset_password(event)
        orga_user.refresh_from_db()
        assert orga_user.pw_reset_token
