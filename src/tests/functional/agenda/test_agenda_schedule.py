import pytest

from pretalx.submission.models import SubmissionStates


@pytest.mark.django_db
def test_can_see_schedule(client, event, slot):
    response = client.get(event.urls.schedule, follow=True)
    assert event.schedules.count() == 2
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_can_see_talk(client, event, slot):
    response = client.get(slot.submission.urls.public, follow=True)
    assert event.schedules.count() == 2
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_cannot_see_nonpublic_talk(client, event, slot):
    event.is_public = False
    event.save()
    response = client.get(slot.submission.urls.public, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_cannot_see_other_events_talk(client, event, slot, other_event):
    response = client.get(slot.submission.urls.public.replace(event.slug, other_event.slug), follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(('state', 'expected_result'), (
    (SubmissionStates.SUBMITTED, 404),
    (SubmissionStates.REJECTED, 404),
    (SubmissionStates.ACCEPTED, 404),
    (SubmissionStates.CONFIRMED, 200),
    (SubmissionStates.CANCELED, 404),
    (SubmissionStates.WITHDRAWN, 404),
))
def test_event_talk_visibility_by_state(client, event, slot, state, expected_result):
    slot.submission.state = state
    slot.submission.save(update_fields=['state'])
    response = client.get(slot.submission.urls.public, follow=True)
    assert response.status_code == expected_result
