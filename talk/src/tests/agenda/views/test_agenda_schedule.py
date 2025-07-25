import textwrap
from urllib.parse import quote

import pytest
from django.urls import reverse
from django_scopes import scope


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
@pytest.mark.parametrize("version,queries", (("js", 6), ("nojs", 8)))
def test_can_see_schedule(
    client, django_assert_num_queries, user, event, slot, version, queries
):
    with scope(event=event):
        del event.current_schedule
        assert user.has_perm("schedule.list_schedule", event)
        url = event.urls.schedule if version == "js" else event.urls.schedule_nojs

    with django_assert_num_queries(queries):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    with scope(event=event):
        assert event.schedules.count() == 2
        test_string = "<pretalx-schedule" if version == "js" else slot.submission.title
        assert test_string in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
@pytest.mark.parametrize("version", ("js", "nojs"))
def test_orga_can_see_wip_schedule(orga_client, event, slot, version):
    with scope(event=event):
        url = event.urls.schedule + "v/wip/"
        if version != "js":
            url += "nojs"
    response = orga_client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    with scope(event=event):
        test_string = "<pretalx-schedule" if version == "js" else slot.submission.title
        assert test_string in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_can_see_text_schedule(client, event, slot):
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="text/plain")
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title[:10] in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("slot", "other_slot")
def test_can_see_schedule_with_broken_accept_header(client, event):
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="foo/bar")
    assert response.status_code == 200
    with scope(event=event):
        assert "<pretalx-schedule" in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("slot", "other_slot")
@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
def test_cannot_see_schedule_by_setting(client, user, event, featured):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()
        assert not user.has_perm("schedule.list_schedule", event)
        event.feature_flags["show_featured"] = featured
        event.save()
    response = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
    if featured == "never":
        assert response.status_code == 404
    else:
        assert response.status_code == 302
        assert response.url == event.urls.featured


@pytest.mark.django_db
@pytest.mark.usefixtures("slot", "other_slot")
@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
def test_cannot_see_no_schedule(client, user, event, featured):
    with scope(event=event):
        event.current_schedule.talks.all().delete()
        event.current_schedule.delete()
        del event.current_schedule
        event.feature_flags["show_featured"] = featured
        event.save()
        assert not user.has_perm("schedule.list_schedule", event)
    response = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
    if featured == "never":
        assert response.status_code == 404
    else:
        assert response.status_code == 302
        assert response.url == event.urls.featured


@pytest.mark.django_db
@pytest.mark.usefixtures("slot", "other_slot")
def test_speaker_list(client, django_assert_num_queries, event, speaker):
    url = event.urls.speakers
    with django_assert_num_queries(9):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_speaker_page(
    client, django_assert_num_queries, event, speaker, slot, other_submission
):
    with scope(event=event):
        other_submission.speakers.add(speaker)
        slot.submission.accept(force=True)
        slot.submission.save()
        event.wip_schedule.freeze("testversion 2")
        other_submission.slots.all().update(is_visible=True)
        slot.submission.slots.all().update(is_visible=True)
    url = reverse("agenda:speaker", kwargs={"code": speaker.code, "event": event.slug})
    with django_assert_num_queries(14):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert len(response.context["talks"]) == 2, response.context["talks"]
    assert response.context["talks"].filter(submission=other_submission)
    with scope(event=event):
        assert speaker.profiles.get(event=event).biography in response.text
        assert slot.submission.title in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_speaker_page_other_submissions_only_if_visible(
    client, django_assert_num_queries, event, speaker, slot, other_submission
):
    with scope(event=event):
        other_submission.speakers.add(speaker)
        slot.submission.accept(force=True)
        slot.submission.save()
        event.wip_schedule.freeze("testversion 2")
        other_submission.slots.all().update(is_visible=False)
        slot.submission.slots.filter(schedule=event.current_schedule).update(
            is_visible=True
        )

    url = reverse("agenda:speaker", kwargs={"code": speaker.code, "event": event.slug})
    with django_assert_num_queries(13):
        response = client.get(url, follow=True)

    assert response.status_code == 200
    assert len(response.context["talks"]) == 1
    assert not response.context["talks"].filter(submission=other_submission)


@pytest.mark.django_db
@pytest.mark.usefixtures("slot")
def test_speaker_social_media(client, django_assert_num_queries, event, speaker):
    url = reverse(
        "agenda:speaker-social", kwargs={"code": speaker.code, "event": event.slug}
    )
    with django_assert_num_queries(10):
        response = client.get(url, follow=True)
    assert response.status_code == 404  # no images available


@pytest.mark.django_db
@pytest.mark.usefixtures("slot", "other_slot")
def test_speaker_redirect(client, event, speaker):
    target_url = reverse(
        "agenda:speaker", kwargs={"code": speaker.code, "event": event.slug}
    )
    url = event.urls.speakers + f"by-id/{speaker.pk}/"
    response = client.get(url)
    assert response.status_code == 302
    assert response.headers["location"].endswith(target_url)


@pytest.mark.django_db
def test_speaker_redirect_unknown(client, event, submission):
    with scope(event=event):
        url = reverse(
            "agenda:speaker.redirect",
            kwargs={"pk": submission.speakers.first().pk, "event": event.slug},
        )
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_schedule_page_text_table(client, django_assert_num_queries, event, slot):
    url = event.urls.schedule
    with django_assert_num_queries(8):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    title_lines = textwrap.wrap(slot.submission.title, width=16)
    content = response.text
    for line in title_lines:
        assert line in content


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_schedule_page_text_table_explicit_header(
    client, django_assert_num_queries, event, slot
):
    url = event.urls.schedule
    with django_assert_num_queries(8):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/plain")
    assert response.status_code == 200
    title_lines = textwrap.wrap(slot.submission.title, width=16)
    content = response.text
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
@pytest.mark.usefixtures("slot", "other_slot")
def test_schedule_page_redirects(
    client, django_assert_num_queries, event, header, target
):
    url = event.urls.schedule
    with django_assert_num_queries(6):
        response = client.get(url, HTTP_ACCEPT=header)
    assert response.status_code == 303
    assert response.headers["location"] == getattr(event.urls, target).full()
    assert response.text == ""


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_schedule_page_text_list(client, django_assert_num_queries, event, slot):
    url = event.urls.schedule
    with django_assert_num_queries(8):
        response = client.get(url, {"format": "list"}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("other_slot")
def test_schedule_page_text_wrong_format(
    client, django_assert_num_queries, event, slot
):
    url = event.urls.schedule
    with django_assert_num_queries(8):
        response = client.get(url, {"format": "wrong"}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title[:10] in response.text


@pytest.mark.django_db
@pytest.mark.parametrize(
    "version,queries_main,queries_versioned,queries_redirect",
    (("js", 6, 8, 13), ("nojs", 7, 12, 16)),
)
@pytest.mark.usefixtures("other_slot")
def test_versioned_schedule_page(
    client,
    django_assert_num_queries,
    django_assert_max_num_queries,
    event,
    slot,
    schedule,
    version,
    queries_main,
    queries_versioned,
    queries_redirect,
):
    with scope(event=event):
        event.release_schedule("new schedule")
        event.current_schedule.talks.update(is_visible=False)
        test_string = "<pretalx-schedule" if version == "js" else slot.submission.title

    url = event.urls.schedule if version == "js" else event.urls.schedule_nojs
    with django_assert_num_queries(queries_main):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    if version == "js":
        # JS widget is displayed even on empty schedules
        assert test_string in response.text
    else:
        # But our talk has been made invisible
        assert test_string not in response.text

    url = schedule.urls.public if version == "js" else schedule.urls.nojs
    with django_assert_max_num_queries(queries_versioned):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    assert test_string in response.text

    url = event.urls.schedule if version == "js" else event.urls.schedule_nojs
    url += f"?version={quote(schedule.version)}"
    with django_assert_num_queries(queries_redirect):
        redirected_response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert redirected_response._request.path == response._request.path
