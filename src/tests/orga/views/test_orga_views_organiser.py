import datetime as dt

import pytest
from django.core import mail as djmail
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretalx.event.models import Event, Organiser


@pytest.mark.django_db
def test_orga_create_organiser(administrator_client):
    assert len(Organiser.objects.all()) == 0
    response = administrator_client.post(
        "/orga/organiser/new",
        data={
            "name_0": "The bestest organiser",
            "name_1": "The bestest organiser",
            "slug": "organiser",
        },
        follow=True,
    )
    assert response.status_code == 200, response.content.decode()
    assert len(Organiser.objects.all()) == 1
    organiser = Organiser.objects.all().first()
    assert str(organiser.name) == "The bestest organiser", response.content.decode()
    assert str(organiser) == str(organiser.name)


@pytest.mark.django_db
def test_orga_edit_organiser(orga_client, organiser):
    response = orga_client.post(
        organiser.orga_urls.base,
        data={"name_0": "The bestest organiser", "name_1": "The bestest organiser"},
        follow=True,
    )
    organiser.refresh_from_db()
    assert response.status_code == 200, response.content.decode()
    assert str(organiser.name) == "The bestest organiser", response.content.decode()
    assert str(organiser) == str(organiser.name)


@pytest.mark.django_db
def test_orga_edit_team(orga_client, organiser, event):
    team = organiser.teams.first()
    url = reverse(
        "orga:organiser.teams.view", kwargs={"organiser": organiser.slug, "pk": team.pk}
    )
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        url,
        follow=True,
        data={
            "all_events": True,
            "can_change_submissions": True,
            "can_change_organiser_settings": True,
            "can_change_event_settings": True,
            "can_change_teams": True,
            "can_create_events": True,
            "form": "team",
            "limit_events": event.pk,
            "name": "Fancy New Name",
        },
    )
    assert response.status_code == 200
    team.refresh_from_db()
    assert team.name == "Fancy New Name"


@pytest.mark.django_db
@pytest.mark.parametrize("is_administrator", [True, False])
def test_orga_create_team(orga_client, organiser, event, is_administrator, orga_user):
    orga_user.is_administrator = is_administrator
    orga_user.save()
    count = organiser.teams.count()
    response = orga_client.get(organiser.orga_urls.new_team, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        organiser.orga_urls.new_team,
        follow=True,
        data={
            "all_events": True,
            "can_change_submissions": True,
            "can_change_organiser_settings": True,
            "can_change_event_settings": True,
            "can_change_teams": True,
            "can_create_events": True,
            "form": "team",
            "limit_events": event.pk,
            "name": "Fancy New Name",
            "organiser": organiser.pk,
        },
    )
    assert response.status_code == 200
    assert organiser.teams.count() == count + 1, response.content.decode()


@pytest.mark.django_db
def test_orga_create_team_without_event(orga_client, organiser, event, orga_user):
    orga_user.is_administrator = True
    orga_user.save()
    count = organiser.teams.count()
    response = orga_client.get(organiser.orga_urls.new_team, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        organiser.orga_urls.new_team,
        follow=True,
        data={
            "can_change_submissions": True,
            "can_change_organiser_settings": True,
            "can_change_event_settings": True,
            "can_change_teams": True,
            "can_create_events": True,
            "form": "team",
            "name": "Fancy New Name",
            "organiser": organiser.pk,
        },
    )
    assert response.status_code == 200
    assert organiser.teams.count() == count


@pytest.mark.django_db
def test_invite_orga_member_as_orga(orga_client, organiser):
    djmail.outbox = []
    team = organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    url = reverse(
        "orga:organiser.teams.view", kwargs={"organiser": organiser.slug, "pk": team.pk}
    )
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        url, {"invite-email": "other@user.org", "form": "invite"}, follow=True
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["other@user.org"]


@pytest.mark.django_db
def test_invite_multiple_orga_members_as_orga(orga_client, organiser):
    djmail.outbox = []
    team = organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    url = reverse(
        "orga:organiser.teams.view", kwargs={"organiser": organiser.slug, "pk": team.pk}
    )
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        url,
        {
            "invite-bulk_email": "first@pretalx.org\nsecond@pretalx.org",
            "form": "invite",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 2
    assert len(djmail.outbox) == 2
    assert djmail.outbox[0].to == ["first@pretalx.org"]
    assert djmail.outbox[1].to == ["second@pretalx.org"]


@pytest.mark.django_db
def test_resend_invite(orga_client, organiser, invitation):
    djmail.outbox = []
    team = invitation.team
    assert team.members.count() == 1
    assert team.invites.count() == 1
    url = reverse(
        "orga:organiser.teams.resend",
        kwargs={"organiser": organiser.slug, "pk": invitation.pk},
    )
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert len(djmail.outbox) == 0

    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == [invitation.email]


@pytest.mark.django_db
def test_reset_team_member_password(orga_client, organiser, other_orga_user):
    djmail.outbox = []
    team = organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    team.members.add(other_orga_user)
    team.save()
    member = team.members.first()
    assert not member.pw_reset_token
    url = organiser.orga_urls.teams + f"{team.pk}/reset/{member.pk}"
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.pw_reset_token
    reset_token = member.pw_reset_token
    assert len(djmail.outbox) == 1

    response = orga_client.post(
        url, follow=True
    )  # make sure we can do this twice despite timeouts
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.pw_reset_token != reset_token
    reset_token = member.pw_reset_token
    assert len(djmail.outbox) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("deadline", (True, False))
class TestEventCreation:
    url = "/orga/event/new/"

    def post(self, step, data, client):
        data = {f"{step}-{key}": value for key, value in data.items()}
        data["event_wizard-current_step"] = step
        response = client.post(self.url, data=data, follow=True)
        assert response.status_code == 200
        return response

    def submit_initial(self, organiser, client):
        return self.post(
            step="initial",
            data={"locales": ["en", "de"], "organiser": organiser.pk},
            client=client,
        )

    def submit_basics(self, client, slug="newevent"):
        return self.post(
            step="basics",
            data={
                "email": "foo@bar.com",
                "locale": "en",
                "name_0": "New event!",
                "slug": slug,
                "timezone": "Europe/Amsterdam",
            },
            client=client,
        )

    def submit_timeline(self, deadline, client):
        _now = now()
        tomorrow = _now + dt.timedelta(days=1)
        date = "%Y-%m-%d"
        datetime = "%Y-%m-%d %H:%M:%S"
        return self.post(
            step="timeline",
            data={
                "date_from": _now.strftime(date),
                "date_to": tomorrow.strftime(date),
                "deadline": _now.strftime(datetime) if deadline else "",
            },
            client=client,
        )

    def submit_display(self, client, **kwargs):
        data = {"header_pattern": "", "logo": "", "primary_color": ""}
        data.update(kwargs)
        return self.post(step="display", data=data, client=client)

    def submit_copy(self, copy=False, client=None):
        return self.post(
            step="copy", data={"copy_from_event": copy if copy else ""}, client=client
        )

    def test_orga_create_event(self, orga_client, organiser, deadline):
        organiser.teams.all().update(can_create_events=True)
        count = Event.objects.count()
        team_count = organiser.teams.count()
        self.submit_initial(organiser, client=orga_client)
        self.submit_basics(client=orga_client, slug=f"newevent{now().year}")
        self.submit_timeline(deadline=deadline, client=orga_client)
        self.submit_display(client=orga_client, header_pattern="topo")
        self.submit_copy(client=orga_client)
        event = Event.objects.get(slug=f"newevent{now().year}")
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count + 1
        assert organiser.teams.filter(
            name__icontains="new"
        ).exists(), organiser.teams.all()
        assert str(event.name) == "New event!"
        assert event.locales == ["en", "de"]
        assert event.content_locales == ["en", "de"]

    def test_orga_create_event_existing_slug(
        self, orga_client, organiser, deadline, event
    ):
        organiser.teams.all().update(can_create_events=True)
        count = Event.objects.count()
        self.submit_initial(organiser, client=orga_client)
        self.submit_basics(client=orga_client, slug=event.slug)
        self.submit_timeline(deadline=deadline, client=orga_client)
        self.submit_display(client=orga_client, header_pattern="topo")
        self.submit_copy(client=orga_client)
        assert Event.objects.count() == count

    def test_orga_create_event_in_the_past(self, orga_client, organiser, deadline):
        organiser.teams.all().update(can_create_events=True)
        count = Event.objects.count()
        team_count = organiser.teams.count()
        self.submit_initial(organiser, client=orga_client)
        self.submit_basics(client=orga_client)
        self.submit_timeline(deadline=deadline, client=orga_client)
        self.submit_display(client=orga_client)
        self.submit_copy(client=orga_client)
        event = Event.objects.get(slug="newevent")
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count + 1
        assert organiser.teams.filter(
            name__icontains="new"
        ).exists(), organiser.teams.all()
        assert str(event.name) == "New event!"
        assert event.locales == ["en", "de"]
        assert event.content_locales == ["en", "de"]

    def test_orga_create_wrong_order(self, orga_client, organiser, deadline):
        organiser.teams.all().update(can_create_events=True)
        self.submit_basics(client=orga_client)

    def test_orga_create_event_with_copy(
        self, orga_client, organiser, event, deadline, question, track
    ):
        organiser.teams.all().update(can_create_events=True)
        count = Event.objects.count()
        event.cfp.fields["title"]["min_length"] = 50
        event.cfp.save()
        team_count = organiser.teams.count()
        self.submit_initial(organiser, client=orga_client)
        self.submit_basics(client=orga_client)
        self.submit_timeline(deadline=deadline, client=orga_client)
        self.submit_display(client=orga_client)
        self.submit_copy(copy=event.pk, client=orga_client)
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count + 1
        assert organiser.teams.filter(
            name__icontains="new"
        ).exists(), organiser.teams.all()
        new_event = Event.objects.exclude(pk=event.pk).first()
        with scopes_disabled():
            assert (
                new_event.cfp.fields["title"]["min_length"]
                == event.cfp.fields["title"]["min_length"]
            )
            assert new_event.questions.all().count()
            assert new_event.tracks.all().count()

    def test_orga_create_event_no_new_team(
        self, orga_client, organiser, event, deadline
    ):
        organiser.teams.update(all_events=True, can_create_events=True)
        count = Event.objects.count()
        team_count = organiser.teams.count()
        self.submit_initial(organiser, client=orga_client)
        self.submit_basics(client=orga_client)
        self.submit_timeline(deadline=deadline, client=orga_client)
        self.submit_display(primary_color="#00ff00", client=orga_client)
        self.submit_copy(client=orga_client)
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count
        assert Event.objects.filter(primary_color="#00ff00").exists()


@pytest.mark.django_db
def test_organiser_cannot_delete_organiser(event, orga_client, submission):
    assert Event.objects.count() == 1
    assert Organiser.objects.count() == 1
    response = orga_client.post(event.organiser.orga_urls.delete, follow=True)
    assert response.status_code == 404
    assert Event.objects.count() == 1
    assert Organiser.objects.count() == 1


@pytest.mark.django_db
def test_administrator_can_delete_organiser(event, administrator_client, submission):
    assert Event.objects.count() == 1
    assert Organiser.objects.count() == 1
    response = administrator_client.get(event.organiser.orga_urls.delete, follow=True)
    assert response.status_code == 200
    response = administrator_client.post(event.organiser.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert Event.objects.count() == 0
    assert Organiser.objects.count() == 0
