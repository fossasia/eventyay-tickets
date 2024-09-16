import textwrap
from urllib.parse import quote

import pytest
from django.urls import reverse
from django_scopes import scope


@pytest.mark.django_db
@pytest.mark.parametrize("version,queries", (("js", 7), ("nojs", 10)))
def test_can_see_schedule(
    client,
    django_assert_num_queries,
    user,
    event,
    slot,
    other_slot,
    version,
    queries,
):
    with scope(event=event):
        del event.current_schedule
        assert user.has_perm("agenda.view_schedule", event)
        url = event.urls.schedule if version == "js" else event.urls.schedule_nojs

    with django_assert_num_queries(queries):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    with scope(event=event):
        assert event.schedules.count() == 2
        test_string = "<pretalx-schedule" if version == "js" else slot.submission.title
        assert test_string in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("version", ("js", "nojs"))
def test_orga_can_see_wip_schedule(
    orga_client, django_assert_num_queries, user, event, slot, other_slot, version
):
    with scope(event=event):
        url = event.urls.schedule + "v/wip/"
        if version != "js":
            url += "nojs"
    response = orga_client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    with scope(event=event):
        test_string = "<pretalx-schedule" if version == "js" else slot.submission.title
        assert test_string in response.content.decode()


@pytest.mark.django_db
def test_can_see_text_schedule(
    client, django_assert_num_queries, user, event, slot, other_slot
):
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="*/*")
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title[:10] in response.content.decode()


@pytest.mark.django_db
def test_can_see_schedule_with_broken_accept_header(
    client, django_assert_num_queries, user, event, slot, other_slot
):
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT="foo/bar")
    assert response.status_code == 200
    with scope(event=event):
        assert "<pretalx-schedule" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("featured", ("always", "never", "pre_schedule"))
def test_cannot_see_schedule_by_setting(
    client, user, event, slot, other_slot, featured
):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()
        assert not user.has_perm("agenda.view_schedule", event)
        event.feature_flags["show_featured"] = featured
        event.save()
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
        event.feature_flags["show_featured"] = featured
        event.save()
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
    with django_assert_num_queries(10):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_speaker_page(
    client,
    django_assert_num_queries,
    event,
    speaker,
    slot,
    other_slot,
    other_submission,
):
    with scope(event=event):
        other_submission.speakers.add(speaker)
        slot.submission.accept(force=True)
        slot.submission.save()
        event.wip_schedule.freeze("testversion 2")
        other_submission.slots.all().update(is_visible=True)
        slot.submission.slots.all().update(is_visible=True)
    url = reverse("agenda:speaker", kwargs={"code": speaker.code, "event": event.slug})
    with django_assert_num_queries(23):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert len(response.context["talks"]) == 2, response.context["talks"]
    assert response.context["talks"].filter(submission=other_submission)
    with scope(event=event):
        assert speaker.profiles.get(event=event).biography in response.content.decode()
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_speaker_page_other_submissions_only_if_visible(
    client,
    django_assert_num_queries,
    event,
    speaker,
    slot,
    other_slot,
    other_submission,
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
    with django_assert_num_queries(18):
        response = client.get(url, follow=True)

    assert response.status_code == 200
    assert len(response.context["talks"]) == 1
    assert not response.context["talks"].filter(submission=other_submission)


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
    assert response.headers["location"].endswith(target_url)


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
def test_schedule_page_text_table(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(8):
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
    with django_assert_num_queries(8):
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
    with django_assert_num_queries(5):
        response = client.get(url, HTTP_ACCEPT=header)
    assert response.status_code == 303
    assert response.headers["location"] == getattr(event.urls, target).full()
    assert response.content.decode() == ""


@pytest.mark.django_db
def test_schedule_page_text_list(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(8):
        response = client.get(url, {"format": "list"}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_schedule_page_text_wrong_format(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(8):
        response = client.get(url, {"format": "wrong"}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title[:10] in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "version,queries_main,queries_versioned", (("js", 7, 8), ("nojs", 8, 11))
)
def test_versioned_schedule_page(
    client,
    django_assert_num_queries,
    event,
    speaker,
    slot,
    schedule,
    other_slot,
    version,
    queries_main,
    queries_versioned,
):
    with scope(event=event):
        event.release_schedule("new schedule")
        event.current_schedule.talks.update(is_visible=False)
        test_string = "<pretalx-schedule" if version == "js" else slot.submission.title

    url = event.urls.schedule if version == "js" else event.urls.schedule_nojs
    with django_assert_num_queries(queries_main):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    if version == "js":
        assert (
            test_string in response.content.decode()
        )  # JS widget is displayed even on empty schedules
    else:
        assert (
            test_string not in response.content.decode()
        )  # But our talk has been made invisible

    url = schedule.urls.public if version == "js" else schedule.urls.nojs
    with django_assert_num_queries(queries_versioned):
        response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    assert test_string in response.content.decode()

    url = event.urls.schedule if version == "js" else event.urls.schedule_nojs
    url += f"?version={quote(schedule.version)}"
    with django_assert_num_queries(queries_versioned + 5):
        redirected_response = client.get(url, follow=True, HTTP_ACCEPT="text/html")
    assert redirected_response._request.path == response._request.path
