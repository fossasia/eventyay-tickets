import datetime as dt
import json

import pytest
from django.conf import settings
from django.core import mail as djmail
from django.utils.timezone import now
from django_scopes import scope

from pretalx.event.models import Event


@pytest.mark.django_db
def test_edit_mail_settings(orga_client, event, availability):
    assert event.mail_settings["mail_from"] != "foo@bar.com"
    assert event.mail_settings["smtp_port"] != 25
    response = orga_client.get(event.orga_urls.mail_settings, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            "mail_from": "foo@bar.com",
            "smtp_host": "localhost",
            "smtp_password": "",
            "smtp_port": "25",
        },
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.mail_settings["mail_from"] == "foo@bar.com"
    assert event.mail_settings["smtp_port"] == 25


@pytest.mark.django_db
def test_fail_unencrypted_mail_settings(orga_client, event, availability):
    assert event.mail_settings["mail_from"] != "foo@bar.com"
    assert event.mail_settings["smtp_port"] != 25
    response = orga_client.get(event.orga_urls.mail_settings, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            "mail_from": "foo@bar.com",
            "smtp_use_custom": True,
            "smtp_host": "foo.bar.com",
            "smtp_password": "",
            "smtp_port": "25",
        },
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.mail_settings["mail_from"] != "foo@bar.com"
    assert event.mail_settings["smtp_port"] != 25


@pytest.mark.django_db
def test_test_mail_settings(orga_client, event, availability):
    assert event.mail_settings["mail_from"] != "foo@bar.com"
    assert event.mail_settings["smtp_port"] != 25
    response = orga_client.get(event.orga_urls.mail_settings, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            "mail_from": "foo@bar.com",
            "smtp_host": "localhost",
            "smtp_password": "",
            "smtp_port": "25",
            "smtp_use_custom": "1",
            "test": "1",
        },
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.mail_settings["mail_from"] == "foo@bar.com"
    assert event.mail_settings["smtp_port"] == 25


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,allowed",
    (
        ("tests/fixtures/custom.css", True),
        ("tests/fixtures/malicious.css", False),
        ("tests/conftest.py", False),
    ),
)
def test_add_custom_css(event, orga_client, path, allowed):
    assert not event.custom_css
    with open(path) as custom_css:
        response = orga_client.post(
            event.orga_urls.edit_settings,
            {
                "name_0": event.name,
                "slug": "csstest",
                "locales": ",".join(event.locales),
                "content_locales": ",".join(event.content_locales),
                "locale": event.locale,
                "date_from": event.date_from,
                "date_to": event.date_to,
                "timezone": event.timezone,
                "email": event.email or "",
                "primary_color": event.primary_color or "",
                "custom_css": custom_css,
                "schedule": event.display_settings["schedule"],
                "show_featured": event.feature_flags["show_featured"],
                "use_feedback": event.feature_flags["use_feedback"],
            },
            follow=True,
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert bool(event.custom_css) == allowed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,allowed",
    (
        ("tests/fixtures/custom.css", True),
        ("tests/fixtures/malicious.css", False),
        ("tests/conftest.py", False),
    ),
)
def test_add_custom_css_as_text(event, orga_client, path, allowed):
    assert not event.custom_css
    with open(path) as custom_css:
        response = orga_client.post(
            event.orga_urls.edit_settings,
            {
                "name_0": event.name,
                "slug": "csstest",
                "locales": ",".join(event.locales),
                "content_locales": ",".join(event.content_locales),
                "locale": event.locale,
                "date_from": event.date_from,
                "date_to": event.date_to,
                "timezone": event.timezone,
                "email": event.email or "",
                "primary_color": event.primary_color or "",
                "custom_css_text": custom_css.read(),
                "schedule": event.display_settings["schedule"],
                "show_featured": event.feature_flags["show_featured"],
                "use_feedback": event.feature_flags["use_feedback"],
            },
            follow=True,
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert bool(event.custom_css) == allowed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    (
        "tests/fixtures/custom.css",
        "tests/fixtures/malicious.css",
        "tests/conftest.py",
    ),
)
def test_add_custom_css_as_administrator(event, administrator_client, path):
    assert not event.custom_css
    with open(path) as custom_css:
        response = administrator_client.post(
            event.orga_urls.edit_settings,
            {
                "name_0": event.name,
                "slug": "csstest",
                "locales": ",".join(event.locales),
                "content_locales": ",".join(event.content_locales),
                "locale": event.locale,
                "date_from": event.date_from,
                "date_to": event.date_to,
                "timezone": event.timezone,
                "email": event.email,
                "primary_color": event.primary_color or "",
                "custom_css": custom_css,
                "schedule": event.display_settings["schedule"],
                "show_featured": event.feature_flags["show_featured"],
                "use_feedback": event.feature_flags["use_feedback"],
            },
            follow=True,
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert event.custom_css


@pytest.mark.django_db
def test_add_logo(event, orga_client):
    assert not event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert '<img loading="lazy" "src="/media' not in response.content.decode()
    with open("../assets/icon.png", "rb") as logo:
        response = orga_client.post(
            event.orga_urls.edit_settings,
            {
                "name_0": event.name,
                "slug": "logotest",
                "locales": event.locales,
                "content_locales": ",".join(event.content_locales),
                "locale": event.locale,
                "date_from": event.date_from,
                "date_to": event.date_to,
                "timezone": event.timezone,
                "email": event.email,
                "primary_color": "#00ff00",
                "logo": logo,
                "schedule": event.display_settings["schedule"],
                "show_featured": event.feature_flags["show_featured"],
                "use_feedback": event.feature_flags["use_feedback"],
            },
            follow=True,
        )
    event.refresh_from_db()
    assert event.primary_color == "#00ff00"
    assert response.status_code == 200
    assert event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert (
        '<img loading="lazy" src="/media' in response.content.decode()
    ), response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "domain,result",
    (
        ("example.org", "https://example.org"),
        ("http://example.org", "https://example.org"),
        ("https://example.org", "https://example.org"),
        (None, None),
    ),
)
def test_change_custom_domain(event, orga_client, monkeypatch, domain, result):
    from pretalx.orga.forms.event import socket

    yessocket = lambda x: True  # noqa
    monkeypatch.setattr(socket, "gethostbyname", yessocket)
    domain = domain or settings.SITE_URL
    assert not event.custom_domain
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            "name_0": event.name,
            "slug": event.slug,
            "locales": event.locales,
            "content_locales": ",".join(event.content_locales),
            "locale": event.locale,
            "date_from": event.date_from,
            "date_to": event.date_to,
            "timezone": event.timezone,
            "email": event.email,
            "primary_color": "",
            "logo": "",
            "custom_domain": domain,
            "schedule": event.display_settings["schedule"],
            "show_featured": event.feature_flags["show_featured"],
            "use_feedback": event.feature_flags["use_feedback"],
        },
        follow=True,
    )
    event = Event.objects.get(pk=event.pk)
    assert response.status_code == 200
    assert event.custom_domain == result


@pytest.mark.django_db
def test_change_custom_domain_to_unavailable_domain(
    event, orga_client, other_event, monkeypatch
):
    from pretalx.orga.forms.event import socket

    def nosocket(param):
        raise OSError

    monkeypatch.setattr(socket, "gethostbyname", nosocket)
    assert not event.custom_domain
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            "name_0": event.name,
            "slug": event.slug,
            "locales": event.locales,
            "content_locales": ",".join(event.content_locales),
            "locale": event.locale,
            "date_from": event.date_from,
            "date_to": event.date_to,
            "timezone": event.timezone,
            "email": event.email,
            "primary_color": "",
            "custom_domain": "https://example.org",
            "schedule": event.display_settings["schedule"],
            "show_featured": event.feature_flags["show_featured"],
            "use_feedback": event.feature_flags["use_feedback"],
        },
        follow=True,
    )
    event = Event.objects.get(pk=event.pk)
    assert response.status_code == 200
    assert not event.custom_domain


@pytest.mark.django_db
def test_event_end_before_start(event, orga_client):
    start = "2022-10-10"
    end = "2022-10-09"
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            "name_0": event.name,
            "slug": "csstest",
            "locales": ",".join(event.locales),
            "content_locales": ",".join(event.content_locales),
            "locale": event.locale,
            "date_from": start,
            "date_to": end,
            "timezone": event.timezone,
            "email": event.email or "",
            "primary_color": event.primary_color or "",
            "schedule": event.display_settings["schedule"],
            "show_featured": event.feature_flags["show_featured"],
            "use_feedback": event.feature_flags["use_feedback"],
        },
        follow=True,
    )
    event.refresh_from_db()
    assert response.status_code == 200
    assert event.date_from.isoformat() != start
    assert event.date_to.isoformat() != end


@pytest.mark.django_db
def test_event_change_date(event, orga_client, slot):
    with scope(event=event):
        wip_slot = (
            event.wip_schedule.talks.all().filter(submission=slot.submission).first()
        )
    old_slot_start = slot.start
    old_wip_slot_start = wip_slot.start
    delta = dt.timedelta(days=17)

    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            "name_0": event.name,
            "slug": "csstest",
            "locales": ",".join(event.locales),
            "content_locales": ",".join(event.content_locales),
            "locale": event.locale,
            "date_from": (event.date_from + delta).isoformat(),
            "date_to": (event.date_to + delta).isoformat(),
            "timezone": event.timezone,
            "email": event.email or "",
            "primary_color": event.primary_color or "",
            "schedule": event.display_settings["schedule"],
            "show_featured": event.feature_flags["show_featured"],
            "use_feedback": event.feature_flags["use_feedback"],
        },
        follow=True,
    )
    assert response.status_code == 200
    slot.refresh_from_db()
    wip_slot.refresh_from_db()
    assert slot.start == old_slot_start
    assert wip_slot.start == old_wip_slot_start + delta


@pytest.mark.django_db
def test_event_change_timezone(event, orga_client, slot):
    old_slot_start = slot.start

    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            "name_0": event.name,
            "slug": "csstest",
            "locales": ",".join(event.locales),
            "content_locales": ",".join(event.content_locales),
            "locale": event.locale,
            "date_from": event.date_from,
            "date_to": event.date_to,
            "timezone": "Europe/Moscow",
            "email": event.email or "",
            "primary_color": event.primary_color or "",
            "schedule": event.display_settings["schedule"],
            "show_featured": event.feature_flags["show_featured"],
            "use_feedback": event.feature_flags["use_feedback"],
        },
        follow=True,
    )
    assert response.status_code == 200
    slot.refresh_from_db()
    assert slot.start != old_slot_start


@pytest.mark.django_db
def test_event_remove_relevant_locales(multilingual_event, orga_client):
    event = multilingual_event
    assert len(event.locales) == 2
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            "name_0": event.name,
            "slug": "csstest",
            "locales": "en",
            "content_locales": "en",
            "locale": "de",
            "date_from": event.date_from,
            "date_to": event.date_to,
            "timezone": event.timezone,
            "email": event.email or "",
            "primary_color": event.primary_color or "",
            "schedule": event.display_settings["schedule"],
            "show_featured": event.feature_flags["show_featured"],
            "use_feedback": event.feature_flags["use_feedback"],
        },
        follow=True,
    )
    event.refresh_from_db()
    assert response.status_code == 200
    assert len(event.locales) == 2


@pytest.mark.django_db
def test_toggle_event_is_public(event, orga_client):
    assert event.is_public
    response = orga_client.get(event.orga_urls.live, follow=True)
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public
    response = orga_client.post(
        event.orga_urls.live, {"action": "activate"}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public
    response = orga_client.post(
        event.orga_urls.live, {"action": "deactivate"}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert not event.is_public
    response = orga_client.post(
        event.orga_urls.live, {"action": "deactivate"}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert not event.is_public
    response = orga_client.post(
        event.orga_urls.live, {"action": "activate"}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public


@pytest.mark.django_db
def test_toggle_event_is_public_without_warnings(
    event, orga_client, default_submission_type, question, submission_type
):
    with scope(event=event):
        event.cfp.text = "a" * 100
        event.cfp.fields["track"]["visbility"] = "optional"
        event.cfp.save()
        event.landing_page_text = "a" * 100
        event.is_public = False
        event.feature_flags["use_track"] = True
        event.save()
    response = orga_client.get(event.orga_urls.live, follow=True)
    assert response.status_code == 200
    event.refresh_from_db()
    assert not event.is_public
    response = orga_client.post(
        event.orga_urls.live, {"action": "activate"}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public


@pytest.mark.django_db
def test_toggle_event_cannot_activate_due_to_plugin(event, orga_client):
    with scope(event=event):
        event.is_public = False
        event.slug = "donottakelive"
        event.plugins = "tests"
        event.save()
    response = orga_client.post(
        event.orga_urls.live, {"action": "activate"}, follow=True
    )
    assert response.status_code == 200
    assert "It's not safe to go alone take this" in response.content.decode()
    event.refresh_from_db()
    assert not event.is_public


@pytest.mark.django_db
def test_toggle_event_can_take_live_with_plugins(event, orga_client):
    with scope(event=event):
        event.is_public = False
        event.plugins = "tests"
        event.save()
    response = orga_client.post(
        event.orga_urls.live, {"action": "activate"}, follow=True
    )
    assert response.status_code == 200
    assert "It's not safe to go alone take this" not in response.content.decode()
    event.refresh_from_db()
    assert event.is_public


@pytest.mark.django_db
def test_invite_orga_member(orga_client, event):
    team = event.organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        team.orga_urls.base,
        {"invite-email": "other@user.org", "form": "invite"},
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1, response.content.decode()
    assert str(team) in str(team.invites.first())


@pytest.mark.django_db
def test_retract_invitation(orga_client, event):
    team = event.organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    response = orga_client.post(
        team.orga_urls.base,
        {"invite-email": "other@user.org", "form": "invite"},
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1, response.content.decode()
    invite = team.invites.first()
    response = orga_client.get(
        team.organiser.orga_urls.teams + f"{invite.id}/uninvite", follow=True
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1, response.content.decode()
    response = orga_client.post(
        team.organiser.orga_urls.teams + f"{invite.id}/uninvite", follow=True
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 0


@pytest.mark.django_db
def test_delete_team_member(orga_client, event, other_orga_user):
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    team.members.add(other_orga_user)
    team.save()
    member = team.members.first()
    count = team.members.count()
    url = team.orga_urls.delete + f"/{member.pk}"
    assert count
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == count
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == count - 1


@pytest.mark.django_db
def test_reset_team_member_password(orga_client, event, other_orga_user):
    djmail.outbox = []
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    team.members.add(other_orga_user)
    team.save()
    member = team.members.first()
    assert not member.pw_reset_token
    url = team.orga_urls.base + f"reset/{member.pk}"
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.pw_reset_token
    assert len(djmail.outbox) == 1
    assert member.pw_reset_token in djmail.outbox[0].body


@pytest.mark.django_db
def test_delete_event_team(orga_client, event):
    count = event.teams.count()
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    response = orga_client.get(team.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert event.teams.count() == count
    response = orga_client.post(team.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert event.teams.count() == count - 1


@pytest.mark.django_db
def test_activate_plugin(event, orga_client, orga_user, monkeypatch):
    plugin_name = "plugin:tests"
    orga_user.is_administrator = True
    orga_user.save()

    assert not event.plugins
    response = orga_client.post(
        event.orga_urls.plugins, follow=True, data={plugin_name: "enable"}
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.plugins == "tests"
    response = orga_client.post(
        event.orga_urls.plugins, follow=True, data={plugin_name: "disable", "bogus": 1}
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.plugins == ""


@pytest.mark.django_db
def test_organiser_cannot_delete_event(event, orga_client, submission):
    assert Event.objects.count() == 1
    response = orga_client.post(event.orga_urls.delete, follow=True)
    assert response.status_code == 404
    assert Event.objects.count() == 1


@pytest.mark.django_db
def test_administrator_can_delete_event(event, administrator_client, submission):
    assert Event.objects.count() == 1
    response = administrator_client.get(event.orga_urls.delete, follow=True)
    assert response.status_code == 200
    response = administrator_client.post(event.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_edit_review_settings(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        assert event.score_categories.count() == 1
        active_phase = event.active_review_phase
        category = event.score_categories.first()
        scores = list(category.scores.all())

    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            "phase-TOTAL_FORMS": 3,
            "phase-INITIAL_FORMS": 2,
            "phase-MIN_NUM_FORMS": 0,
            "phase-MAX_NUM_FORMS": 1000,
            "phase-0-name": active_phase.name + "xxx",
            "phase-0-id": active_phase.id,
            "phase-0-start": "",
            "phase-0-end": "",
            "phase-0-can_see_other_reviews": "after_review",
            "phase-0-can_tag_submissions": "use_tags",
            "phase-0-proposal_visibility": "all",
            "phase-1-name": active_phase.name + "xxxy",
            "phase-1-id": active_phase.id + 1,
            "phase-1-start": "",
            "phase-1-end": "",
            "phase-1-can_see_other_reviews": "after_review",
            "phase-1-can_tag_submissions": "use_tags",
            "phase-1-proposal_visibility": "all",
            "phase-2-name": active_phase.name + "xxxyz",
            "phase-2-start": "",
            "phase-2-end": "",
            "phase-2-can_see_other_reviews": "after_review",
            "phase-2-can_tag_submissions": "use_tags",
            "phase-2-proposal_visibility": "all",
            "scores-TOTAL_FORMS": "1",
            "scores-INITIAL_FORMS": "1",
            "scores-MIN_NUM_FORMS": "0",
            "scores-MAX_NUM_FORMS": "1000",
            "scores-0-name_0": str(category.name) + "xxx",
            "scores-0-id": category.id,
            "scores-0-weight": "1",
            "scores-0-is_independent": "on",
            f"scores-0-value_{scores[0].id}": scores[0].value,
            f"scores-0-label_{scores[0].id}": scores[0].label,
            f"scores-0-value_{scores[1].id}": scores[1].value,
            f"scores-0-label_{scores[1].id}": scores[1].label,
            f"scores-0-value_{scores[2].id}": scores[2].value,
            f"scores-0-label_{scores[2].id}": scores[2].label,
            "aggregate_method": event.review_settings["aggregate_method"],
            "score_format": event.review_settings["score_format"],
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        # Did not save
        assert event.score_categories.filter(is_independent=False).exists()
        assert "non-independent" in response.content.decode()


@pytest.mark.django_db
def test_edit_review_settings_no_independent_category(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        assert event.score_categories.count() == 1
        active_phase = event.active_review_phase
        category = event.score_categories.first()
        scores = list(category.scores.all())

    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            "phase-TOTAL_FORMS": 3,
            "phase-INITIAL_FORMS": 2,
            "phase-MIN_NUM_FORMS": 0,
            "phase-MAX_NUM_FORMS": 1000,
            "phase-0-name": active_phase.name + "xxx",
            "phase-0-id": active_phase.id,
            "phase-0-start": "",
            "phase-0-end": "",
            "phase-0-can_see_other_reviews": "after_review",
            "phase-0-can_tag_submissions": "use_tags",
            "phase-0-proposal_visibility": "all",
            "phase-1-name": active_phase.name + "xxxy",
            "phase-1-id": active_phase.id + 1,
            "phase-1-start": "",
            "phase-1-end": "",
            "phase-1-can_see_other_reviews": "after_review",
            "phase-1-can_tag_submissions": "use_tags",
            "phase-1-proposal_visibility": "all",
            "phase-2-name": active_phase.name + "xxxyz",
            "phase-2-start": "",
            "phase-2-end": "",
            "phase-2-can_see_other_reviews": "after_review",
            "phase-2-can_tag_submissions": "use_tags",
            "phase-2-proposal_visibility": "all",
            "scores-TOTAL_FORMS": "1",
            "scores-INITIAL_FORMS": "1",
            "scores-MIN_NUM_FORMS": "0",
            "scores-MAX_NUM_FORMS": "1000",
            "scores-0-name_0": str(category.name) + "xxx",
            "scores-0-id": category.id,
            "scores-0-weight": "1",
            f"scores-0-value_{scores[0].id}": scores[0].value,
            f"scores-0-label_{scores[0].id}": scores[0].label,
            f"scores-0-value_{scores[1].id}": scores[1].value,
            f"scores-0-label_{scores[1].id}": scores[1].label,
            f"scores-0-value_{scores[2].id}": scores[2].value,
            f"scores-0-label_{scores[2].id}": scores[2].label,
            "aggregate_method": event.review_settings["aggregate_method"],
            "score_format": event.review_settings["score_format"],
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.review_phases.count() == 3
        assert event.review_phases.filter(name=active_phase.name + "xxx").exists()
        assert event.score_categories.filter(name__contains="xxx").exists()
        assert event.score_categories.count() == 1


@pytest.mark.django_db
def test_edit_review_settings_invalid(orga_client, event):
    assert event.settings.review_score_names is None
    with scope(event=event):
        active_phase = event.active_review_phase
        category = event.score_categories.first()
        scores = list(category.scores.all())
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            "phase-TOTAL_FORMS": 2,
            "phase-INITIAL_FORMS": 2,
            "phase-MIN_NUM_FORMS": 0,
            "phase-MAX_NUM_FORMS": 1000,
            "phase-0-name": active_phase.name + "xxx",
            "phase-0-id": active_phase.id,
            "phase-0-start": "",
            "phase-0-end": "",
            "phase-0-can_see_other_reviews": "after_review",
            "phase-0-can_tag_submissions": "hahah",
            "phase-0-proposal_visibility": "all",
            "phase-1-name": active_phase.name + "xxxy",
            "phase-1-id": active_phase.id + 1,
            "phase-1-start": "",
            "phase-1-end": "",
            "phase-1-can_see_other_reviews": "after_review",
            "phase-1-can_tag_submissions": "use_tags",
            "phase-1-proposal_visibility": "all",
            "scores-TOTAL_FORMS": "1",
            "scores-INITIAL_FORMS": "1",
            "scores-MIN_NUM_FORMS": "0",
            "scores-MAX_NUM_FORMS": "1000",
            "scores-0-name_0": str(category.name) + "xxx",
            "scores-0-id": category.id,
            "scores-0-weight": "1",
            f"scores-0-value_{scores[0].id}": scores[0].value,
            f"scores-0-label_{scores[0].id}": scores[0].label,
            f"scores-0-value_{scores[1].id}": scores[1].value,
            f"scores-0-label_{scores[1].id}": scores[1].label,
            f"scores-0-value_{scores[2].id}": scores[2].value,
            f"scores-0-label_{scores[2].id}": scores[2].label,
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.review_phases.count() == 2
        assert not event.review_phases.filter(name=active_phase.name + "xxx").exists()


@pytest.mark.django_db
def test_edit_review_settings_invalid_formset(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        active_phase = event.active_review_phase
        category = event.score_categories.first()
        scores = list(category.scores.all())
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            "phase-TOTAL_FORMS": 2,
            "phase-INITIAL_FORMS": 2,
            "phase-MIN_NUM_FORMS": 0,
            "phase-MAX_NUM_FORMS": 1000,
            "phase-0-name": active_phase.name + "xxx",
            "phase-0-id": active_phase.id,
            "phase-0-start": "lalala",
            "phase-0-end": "",
            "phase-0-can_see_other_reviews": "after_review",
            "phase-0-can_tag_submissions": "use_tags",
            "phase-0-proposal_visibility": "all",
            "phase-1-name": active_phase.name + "xxxy",
            "phase-1-id": active_phase.id + 1,
            "phase-1-start": "",
            "phase-1-end": "",
            "phase-1-can_see_other_reviews": "after_review",
            "phase-1-can_tag_submissions": "use_tags",
            "phase-1-proposal_visibility": "all",
            "scores-TOTAL_FORMS": "1",
            "scores-INITIAL_FORMS": "1",
            "scores-MIN_NUM_FORMS": "0",
            "scores-MAX_NUM_FORMS": "1000",
            "scores-0-name_0": str(category.name) + "xxx",
            "scores-0-id": category.id,
            "scores-0-weight": "1",
            f"scores-0-value_{scores[0].id}": scores[0].value,
            f"scores-0-label_{scores[0].id}": scores[0].label,
            f"scores-0-value_{scores[1].id}": scores[1].value,
            f"scores-0-label_{scores[1].id}": scores[1].label,
            f"scores-0-value_{scores[2].id}": scores[2].value,
            f"scores-0-label_{scores[2].id}": scores[2].label,
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.review_phases.count() == 2
        assert not event.review_phases.filter(name=active_phase.name + "xxx").exists()


@pytest.mark.django_db
def test_edit_review_settings_new_review_phase(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        active_phase = event.active_review_phase
        category = event.score_categories.first()
        scores = list(category.scores.all())
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            "phase-TOTAL_FORMS": 3,
            "phase-INITIAL_FORMS": 2,
            "phase-MIN_NUM_FORMS": 0,
            "phase-MAX_NUM_FORMS": 1000,
            "phase-0-name": active_phase.name + "xxx",
            "phase-0-id": active_phase.id,
            "phase-0-start": "",
            "phase-0-end": "",
            "phase-0-can_see_other_reviews": "after_review",
            "phase-0-can_tag_submissions": "use_tags",
            "phase-0-proposal_visibility": "all",
            "phase-1-name": active_phase.name + "xxxy",
            "phase-1-id": active_phase.id + 1,
            "phase-1-start": "",
            "phase-1-end": "",
            "phase-1-can_see_other_reviews": "after_review",
            "phase-1-can_tag_submissions": "use_tags",
            "phase-1-proposal_visibility": "all",
            "phase-2-name": "New Review Phase",
            "phase-2-start": "",
            "phase-2-end": "",
            "phase-2-can_see_other_reviews": "always",
            "phase-2-can_tag_submissions": "use_tags",
            "phase-2-proposal_visibility": "all",
            "scores-TOTAL_FORMS": "1",
            "scores-INITIAL_FORMS": "1",
            "scores-MIN_NUM_FORMS": "0",
            "scores-MAX_NUM_FORMS": "1000",
            "scores-0-name_0": str(category.name) + "xxx",
            "scores-0-id": category.id,
            "scores-0-weight": "1",
            f"scores-0-value_{scores[0].id}": scores[0].value,
            f"scores-0-label_{scores[0].id}": scores[0].label,
            f"scores-0-value_{scores[1].id}": scores[1].value,
            f"scores-0-label_{scores[1].id}": scores[1].label,
            f"scores-0-value_{scores[2].id}": scores[2].value,
            f"scores-0-label_{scores[2].id}": scores[2].label,
            "aggregate_method": event.review_settings["aggregate_method"],
            "score_format": event.review_settings["score_format"],
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.review_phases.count() == 3


@pytest.mark.django_db
def test_edit_review_settings_new_review_phase_wrong_dates(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        active_phase = event.active_review_phase
        category = event.score_categories.first()
        scores = list(category.scores.all())
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            "phase-TOTAL_FORMS": 3,
            "phase-INITIAL_FORMS": 2,
            "phase-MIN_NUM_FORMS": 0,
            "phase-MAX_NUM_FORMS": 1000,
            "phase-0-name": active_phase.name + "xxx",
            "phase-0-id": active_phase.id,
            "phase-0-start": "",
            "phase-0-end": "",
            "phase-0-can_see_other_reviews": "after_review",
            "phase-0-can_tag_submissions": "use_tags",
            "phase-0-proposal_visibility": "all",
            "phase-1-name": active_phase.name + "xxxy",
            "phase-1-id": active_phase.id + 1,
            "phase-1-start": "",
            "phase-1-end": "",
            "phase-1-can_see_other_reviews": "after_review",
            "phase-1-can_tag_submissions": "use_tags",
            "phase-1-proposal_visibility": "all",
            "phase-2-name": "New Review Phase",
            "phase-2-start": now().strftime("%Y-%m-%d"),
            "phase-2-end": (now() - dt.timedelta(days=7)).strftime("%Y-%m-%d"),
            "phase-2-can_see_other_reviews": "always",
            "phase-2-can_tag_submissions": "use_tags",
            "phase-2-proposal_visibility": "all",
            "scores-TOTAL_FORMS": "1",
            "scores-INITIAL_FORMS": "1",
            "scores-MIN_NUM_FORMS": "0",
            "scores-MAX_NUM_FORMS": "1000",
            "scores-0-name_0": str(category.name) + "xxx",
            "scores-0-id": category.id,
            "scores-0-weight": "1",
            f"scores-0-value_{scores[0].id}": scores[0].value,
            f"scores-0-label_{scores[0].id}": scores[0].label,
            f"scores-0-value_{scores[1].id}": scores[1].value,
            f"scores-0-label_{scores[1].id}": scores[1].label,
            f"scores-0-value_{scores[2].id}": scores[2].value,
            f"scores-0-label_{scores[2].id}": scores[2].label,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert "The end of a phase has to be after its start." in response.content.decode()
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.review_phases.count() == 2


@pytest.mark.django_db
def test_edit_review_settings_delete_review_phase(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.first()
    response = orga_client.get(phase.urls.delete, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.review_phases.count() == 1


@pytest.mark.django_db
def test_edit_review_settings_activate_review_phase(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.active_review_phase
        other_phase = event.review_phases.exclude(pk=phase.pk).first()
    response = orga_client.get(other_phase.urls.activate, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.active_review_phase == other_phase


@pytest.mark.django_db
def test_edit_review_settings_move_review_phase_down(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.first()
    assert phase.position == 0
    response = orga_client.get(phase.urls.down, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        phase.refresh_from_db()
    assert phase.position == 1


@pytest.mark.django_db
def test_edit_review_settings_move_review_phase_up(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.last()
    assert phase.position == 1
    response = orga_client.get(phase.urls.up, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        phase.refresh_from_db()
    assert phase.position == 0


@pytest.mark.django_db
def test_edit_review_settings_move_review_phase_up_out_of_bounds(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.first()
    assert phase.position == 0
    response = orga_client.get(phase.urls.up, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        phase.refresh_from_db()
    assert phase.position == 0


@pytest.mark.django_db
def test_edit_review_settings_move_review_phase_down_out_of_bounds(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.last()
    assert phase.position == 1
    response = orga_client.get(phase.urls.down, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        phase.refresh_from_db()
    assert phase.position == 1


@pytest.mark.django_db
def test_edit_review_settings_move_wrong_review_phase(orga_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.last()
    assert phase.position == 1
    response = orga_client.get(
        phase.urls.down.replace(str(phase.pk), str(phase.pk + 100)), follow=True
    )
    assert response.status_code == 404
    with scope(event=event):
        phase.refresh_from_db()
    assert phase.position == 1


@pytest.mark.django_db
def test_edit_review_settings_reviewer_cannot_move_review_phase(review_client, event):
    with scope(event=event):
        assert event.review_phases.count() == 2
        phase = event.review_phases.first()
    assert phase.position == 0
    response = review_client.get(phase.urls.down, follow=True)
    assert response.status_code == 404
    with scope(event=event):
        phase.refresh_from_db()
    assert phase.position == 0


@pytest.mark.django_db
def test_organiser_can_see_event_suggestions(orga_client, event):
    response = orga_client.get("/orga/nav/typeahead/")
    assert response.status_code == 200
    content = json.loads(response.content.decode())["results"]
    assert len(content) == 3
    assert content[0]["type"] == "user"
    assert content[1]["type"] == "organiser"
    assert content[1]["name"] == str(event.organiser)
    assert content[2]["type"] == "event"
    assert content[2]["name"] == str(event.name)


@pytest.mark.django_db
def test_speaker_cannot_see_event_suggestions(speaker_client, event):
    response = speaker_client.get("/orga/nav/typeahead/")
    assert response.status_code == 200
    content = json.loads(response.content.decode())["results"]
    assert len(content) == 1
    assert content[0]["type"] == "user"


@pytest.mark.django_db
def test_widget_settings(event, orga_client):
    assert not event.feature_flags["show_widget_if_not_public"]
    response = orga_client.get(event.orga_urls.widget_settings, follow=True)
    response = orga_client.post(
        event.orga_urls.widget_settings,
        {
            "show_widget_if_not_public": "on",
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert event.feature_flags["show_widget_if_not_public"]
