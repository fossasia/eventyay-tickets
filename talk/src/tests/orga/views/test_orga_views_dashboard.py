import datetime as dt

import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope


@pytest.mark.parametrize("test_user", ("orga", "speaker", "superuser", "None"))
@pytest.mark.parametrize("query", ("", "?q=e"))
@pytest.mark.django_db
def test_dashboard_event_list(
    orga_user, orga_client, speaker, event, other_event, test_user, slot, query
):
    if test_user == "speaker":
        orga_client.force_login(speaker)
    elif test_user == "None":
        orga_client.logout()
    elif test_user == "superuser":
        orga_user.is_administrator = True
        orga_user.save()

    response = orga_client.get(reverse("orga:event.list") + query, follow=True)

    if test_user == "speaker":
        assert response.status_code == 200
        assert event.slug not in response.content.decode()
    elif test_user == "orga":
        assert response.status_code == 200
        assert event.slug in response.content.decode()
        assert other_event.slug not in response.content.decode()
    elif test_user == "superuser":
        assert response.status_code == 200
        assert event.slug in response.content.decode(), response.content.decode()
        assert other_event.slug in response.content.decode(), response.content.decode()
    else:
        current_url = response.redirect_chain[-1][0]
        assert "login" in current_url


@pytest.mark.parametrize(
    "test_user", ("orga", "speaker", "superuser", "reviewer", "None")
)
@pytest.mark.parametrize("query", ("", "?q=e"))
@pytest.mark.django_db
def test_event_dashboard(
    orga_user, orga_client, review_user, speaker, event, test_user, slot, query
):
    from pretalx.common.models.log import ActivityLog

    ActivityLog.objects.create(
        event=event,
        person=speaker,
        content_object=slot.submission,
        action_type="pretalx.submission.create",
    )
    if test_user == "speaker":
        orga_client.force_login(speaker)
    elif test_user == "None":
        orga_client.logout()
    elif test_user == "superuser":
        orga_user.is_administrator = True
        orga_user.save()
    elif test_user == "reviewer":
        with scope(event=event):
            event.active_review_phase.can_see_speaker_names = False
            event.active_review_phase.save()
        orga_client.force_login(review_user)

    response = orga_client.get(event.orga_urls.base + query, follow=True)

    if test_user == "speaker":
        assert response.status_code == 404
        assert event.slug not in response.content.decode()
    elif test_user == "orga":
        assert response.status_code == 200
        assert event.slug in response.content.decode()
        assert speaker.name in response.content.decode()
    elif test_user == "superuser":
        assert response.status_code == 200
        assert event.slug in response.content.decode(), response.content.decode()
        assert speaker.name in response.content.decode()
    elif test_user == "reviewer":
        assert not review_user.has_perm("orga.view_speakers", event)
        assert response.status_code == 200
        assert event.slug in response.content.decode(), response.content.decode()
        assert speaker.name not in response.content.decode()
    else:
        current_url = response.redirect_chain[-1][0]
        assert "login" in current_url


@pytest.mark.parametrize("test_user", ("orga", "speaker", "superuser", "None"))
@pytest.mark.django_db
def test_dashboard_organiser_list(
    orga_user, orga_client, speaker, event, other_event, test_user
):
    if test_user == "speaker":
        orga_client.force_login(speaker)
    elif test_user == "None":
        orga_client.logout()
    elif test_user == "superuser":
        orga_user.is_administrator = True
        orga_user.save()

    response = orga_client.get(reverse("orga:organiser.list"), follow=True)

    if test_user == "speaker":
        assert response.status_code == 404, response.status_code
    elif test_user == "orga":
        assert event.organiser.name in response.content.decode()
        assert other_event.organiser.name not in response.content.decode()
    elif test_user == "superuser":
        assert (
            event.organiser.name in response.content.decode()
        ), response.content.decode()
        assert (
            other_event.organiser.name in response.content.decode()
        ), response.content.decode()
    else:
        current_url = response.redirect_chain[-1][0]
        assert "login" in current_url


@pytest.mark.django_db
def test_event_dashboard_with_talks(event, orga_client, review_user, review, slot):
    with scope(event=event):
        event.cfp.deadline = now()
        event.save()
    response = orga_client.get(event.orga_urls.base)
    assert response.status_code == 200


@pytest.mark.django_db
def test_event_dashboard_with_accepted(
    event, orga_client, review_user, review, slot, accepted_submission
):
    with scope(event=event):
        event.cfp.deadline = now()
        event.save()
    response = orga_client.get(event.orga_urls.base)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start_diff,end_diff",
    (
        (0, 0),
        (-3, -3),
        (3, 3),
    ),
)
def test_event_dashboard_different_times(event, orga_client, start_diff, end_diff):
    with scope(event=event):
        today = now().date()
        event.date_from = today + dt.timedelta(days=start_diff)
        event.date_end = today + dt.timedelta(days=end_diff)
        event.save()
    response = orga_client.get(event.orga_urls.base)
    assert response.status_code == 200
