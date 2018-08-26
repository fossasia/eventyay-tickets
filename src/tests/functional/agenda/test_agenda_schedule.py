from urllib.parse import quote

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_can_see_schedule(client, user, event, slot):
    del event.current_schedule
    assert user.has_perm('agenda.view_schedule', event)
    response = client.get(event.urls.schedule, follow=True)
    assert event.schedules.count() == 2
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_speaker_list(client, event, speaker, slot):
    response = client.get(event.urls.speakers, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_speaker_page(client, event, speaker, slot):
    response = client.get(
        reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug}),
        follow=True,
    )
    assert response.status_code == 200
    assert speaker.profiles.get(event=event).biography in response.content.decode()


@pytest.mark.django_db
def test_schedule_page(client, event, speaker, slot, schedule):
    response = client.get(event.urls.schedule, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_versioned_schedule_page(client, event, speaker, slot, schedule):
    event.release_schedule('new schedule')
    event.current_schedule.talks.update(is_visible=False)

    response = client.get(event.urls.schedule, follow=True)
    assert slot.submission.title not in response.content.decode()

    response = client.get(schedule.urls.public, follow=True)
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()

    version = quote(schedule.version)
    redirected_response = client.get(
        f'/{event.slug}/schedule?version={version}', follow=True
    )
    assert redirected_response._request.path == response._request.path
