import textwrap
from urllib.parse import quote

import pytest
from django.urls import reverse
from django_scopes import scope


@pytest.mark.django_db
@pytest.mark.parametrize("layout", ("proportional", "list"))
def test_can_see_schedule(
    client, django_assert_num_queries, user, event, slot, other_slot, layout
):
    with scope(event=event):
        del event.current_schedule
        event.settings.schedule_display = layout
        assert user.has_perm("agenda.view_schedule", event)
    with django_assert_num_queries(20):
        response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    with scope(event=event):
        assert event.schedules.count() == 2
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("layout", ("proportional", "list"))
def test_orga_can_see_wip_schedule(
    orga_client, django_assert_num_queries, user, event, slot, other_slot, layout
):
    with scope(event=event):
        event.settings.schedule_display = layout
    response = orga_client.get(
        event.urls.schedule + "v/wip/", follow=True, HTTP_ACCEPT="text/html"
    )
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_can_see_text_schedule(
    client, django_assert_num_queries, user, event, slot, other_slot
):
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="*/*")
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title[:10] in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("layout", ("proportional", "list"))
def test_can_see_schedule_with_broken_accept_header(
    client, django_assert_num_queries, user, event, slot, other_slot, layout
):
    with scope(event=event):
        event.settings.schedule_display = layout
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="foo/bar")
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
def test_cannot_see_schedule_by_setting(
    client, user, event, slot, other_slot, featured
):
    with scope(event=event):
        event.settings.show_schedule = False
        assert not user.has_perm("agenda.view_schedule", event)
        event.settings.show_featured = featured
    response = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
    if featured == "never":
        assert response.status_code == 404
    else:
        assert response.status_code == 302
        assert response.url == event.urls.featured


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
def test_cannot_see_no_schedule(client, user, event, slot, other_slot, featured):
    with scope(event=event):
        event.current_schedule.talks.all().delete()
        event.current_schedule.delete()
        del event.current_schedule
        event.settings.show_featured = featured
        assert not user.has_perm("agenda.view_schedule", event)
    response = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
    if featured == "never":
        assert response.status_code == 404
    else:
        assert response.status_code == 302
        assert response.url == event.urls.featured


@pytest.mark.django_db
def test_speaker_list(
    client, django_assert_num_queries, event, speaker, slot, other_slot
):
    url = event.urls.speakers
    with django_assert_num_queries(19):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_speaker_page(
    client, django_assert_num_queries, event, speaker, slot, other_slot
):
    url = reverse("agenda:speaker", kwargs={"code": speaker.code, "event": event.slug})
    with django_assert_num_queries(25):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert speaker.profiles.get(event=event).biography in response.content.decode()
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_speaker_redirect(
    client, django_assert_num_queries, event, speaker, slot, other_slot
):
    target_url = reverse(
        "agenda:speaker", kwargs={"code": speaker.code, "event": event.slug}
    )
    url = event.urls.speakers + f"by-id/{speaker.pk}/"
    response = client.get(url)
    assert response.status_code == 302
    assert response._headers["location"][1].endswith(target_url)


@pytest.mark.django_db
def test_speaker_redirect_unknown(client, django_assert_num_queries, event, submission):
    with scope(event=event):
        url = reverse(
            "agenda:speaker.redirect",
            kwargs={"pk": submission.speakers.first().pk, "event": event.slug},
        )
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_schedule_page(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(20):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_schedule_page_text_table(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    title_lines = textwrap.wrap(slot.submission.title, width=16)
    content = response.content.decode()
    for line in title_lines:
        assert line in content


@pytest.mark.django_db
def test_schedule_page_text_table_explicit_header(
    client,
    django_assert_num_queries,
    event,
    speaker,
    slot,
    schedule,
    other_slot,
):
    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/plain")
    assert response.status_code == 200
    title_lines = textwrap.wrap(slot.submission.title, width=16)
    content = response.content.decode()
    for line in title_lines:
        assert line in content


@pytest.mark.parametrize(
    "header,target",
    (
        ("application/json", "frab_json"),
        ("application/xml", "frab_xml"),
    ),
)
@pytest.mark.django_db
def test_schedule_page_redirects(
    client,
    django_assert_num_queries,
    event,
    speaker,
    slot,
    schedule,
    other_slot,
    header,
    target,
):
    url = event.urls.schedule
    with django_assert_num_queries(16):
        response = client.get(url, HTTP_ACCEPT=header)
    assert response.status_code == 303
    assert response._headers["location"][1] == getattr(event.urls, target).full()
    assert response.content.decode() == ""


@pytest.mark.django_db
def test_schedule_page_text_list(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, {"format": "list"}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_schedule_page_text_wrong_format(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, {"format": "wrong"}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title[:10] in response.content.decode()


@pytest.mark.django_db
def test_versioned_schedule_page(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    with scope(event=event):
        event.release_schedule("new schedule")
        event.current_schedule.talks.update(is_visible=False)

    url = event.urls.schedule
    with django_assert_num_queries(19):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    with scope(event=event):
        assert slot.submission.title not in response.content.decode()

    url = schedule.urls.public
    with django_assert_num_queries(15):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title in response.content.decode()

    url = f"/{event.slug}/schedule?version={quote(schedule.version)}"
    with django_assert_num_queries(25):
        redirected_response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert redirected_response._request.path == response._request.path
