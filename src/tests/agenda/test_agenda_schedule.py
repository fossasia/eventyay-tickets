from urllib.parse import quote

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_can_see_schedule(
    client, django_assert_num_queries, user, event, slot, other_slot
):
    del event.current_schedule
    assert user.has_perm('agenda.view_schedule', event)
    with django_assert_num_queries(18):
        response = client.get(event.urls.schedule, follow=True)
    assert event.schedules.count() == 2
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_speaker_list(
    client, django_assert_num_queries, event, speaker, slot, other_slot
):
    url = event.urls.speakers
    with django_assert_num_queries(23):
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
    assert speaker.profiles.get(event=event).biography in response.content.decode()


@pytest.mark.django_db
def test_schedule_page(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    url = event.urls.schedule
    with django_assert_num_queries(18):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_versioned_schedule_page(
    client, django_assert_num_queries, event, speaker, slot, schedule, other_slot
):
    event.release_schedule('new schedule')
    event.current_schedule.talks.update(is_visible=False)

    url = event.urls.schedule
    with django_assert_num_queries(17):
        response = client.get(url, follow=True)
    assert slot.submission.title not in response.content.decode()

    url = schedule.urls.public
    with django_assert_num_queries(13):
        response = client.get(url, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()

    url = f'/{event.slug}/schedule?version={quote(schedule.version)}'
    with django_assert_num_queries(20):
        redirected_response = client.get(url, follow=True)
    assert redirected_response._request.path == response._request.path
