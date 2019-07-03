import textwrap
from urllib.parse import quote

import pytest
from django.urls import reverse
from django_scopes import scope


@pytest.mark.django_db
def test_can_see_schedule(
    client, django_assert_num_queries, user, event, slot, other_slot
):
    with scope(event=event):
        del event.current_schedule
        assert user.has_perm('agenda.view_schedule', event)
    with django_assert_num_queries(19):
        response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    with scope(event=event):
        assert event.schedules.count() == 2
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('sneak_peek', (True, False))
def test_cannot_see_schedule_by_setting(client, user, event, slot, other_slot, sneak_peek):
    with scope(event=event):
        event.settings.show_schedule = False
        assert not user.has_perm('agenda.view_schedule', event)
        event.settings.show_sneak_peek = sneak_peek
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT='text/html')
    assert response.status_code == (404 if not sneak_peek else 200)
    if sneak_peek:
        assert response.redirect_chain == [(event.urls.sneakpeek, 302)]


@pytest.mark.django_db
@pytest.mark.parametrize('sneak_peek', (True, False))
def test_cannot_see_no_schedule(client, user, event, slot, other_slot, sneak_peek):
    with scope(event=event):
        event.current_schedule.talks.all().delete()
        event.current_schedule.delete()
        del event.current_schedule
        event.settings.show_sneak_peek = sneak_peek
        assert not user.has_perm('agenda.view_schedule', event)
    response = client.get(event.urls.schedule, follow=True, HTTP_ACCEPT='text/html')
    assert response.status_code == (404 if not sneak_peek else 200)
    if sneak_peek:
        assert response.redirect_chain == [(event.urls.sneakpeek, 302)]


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
    url = reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug})
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
    target = reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug})
    url = reverse('agenda:speaker.redirect', kwargs={'pk': speaker.pk, 'event': event.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert response.url.endswith(target)


@pytest.mark.django_db
def test_schedule_page(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(19):
        response = client.get(url, follow=True, HTTP_ACCEPT='text/html')
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
def test_schedule_page_text_list(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, {'format': 'list'}, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_versioned_schedule_page(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    with scope(event=event):
        event.release_schedule('new schedule')
        event.current_schedule.talks.update(is_visible=False)

    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, follow=True, HTTP_ACCEPT='text/html')
    with scope(event=event):
        assert slot.submission.title not in response.content.decode()

    url = schedule.urls.public
    with django_assert_num_queries(14):
        response = client.get(url, follow=True, HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title in response.content.decode()

    url = f'/{event.slug}/schedule?version={quote(schedule.version)}'
    with django_assert_num_queries(24):
        redirected_response = client.get(url, follow=True, HTTP_ACCEPT='text/html')
    assert redirected_response._request.path == response._request.path
