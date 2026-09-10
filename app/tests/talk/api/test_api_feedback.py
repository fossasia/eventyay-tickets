import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.base.models import Feedback


def _enable_feedback(event, **flags):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        for key, value in flags.items():
            event.feature_flags[key] = value
        event.save(update_fields=['feature_flags'])


@pytest.mark.django_db
def test_feedback_list_requires_authentication(client, past_slot, feedback):
    event = past_slot.submission.event
    submission = past_slot.submission
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = client.get(url + f'?talk={submission.code}')
    assert response.status_code == 403


@pytest.mark.django_db
def test_feedback_list_authenticated(orga_client, past_slot, feedback):
    submission = past_slot.submission
    event = submission.event
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = orga_client.get(url + f'?talk={submission.code}')
    assert response.status_code == 200
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['review'] == feedback.review


@pytest.mark.django_db
def test_feedback_create(client, past_slot, user):
    submission = past_slot.submission
    event = submission.event
    _enable_feedback(
        event,
        feedback_who_can_comment='registered',
        feedback_close_after_days=0,
    )
    client.force_login(user)
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = client.post(
        url,
        {
            'talk': submission.code,
            'review': 'Great talk!',
            'is_public': True,
        },
    )
    assert response.status_code == 201
    assert Feedback.objects.count() == 1
    assert Feedback.objects.first().review == 'Great talk!'
    assert Feedback.objects.first().author == user


@pytest.mark.django_db
def test_feedback_create_unauthenticated(client, past_slot):
    submission = past_slot.submission
    event = submission.event
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = client.post(
        url,
        {
            'talk': submission.code,
            'review': 'Great talk!',
            'is_public': True,
        },
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_feedback_create_when_disabled(client, past_slot, user):
    """Verify feedback API rejects creation when feedback is disabled by default."""
    submission = past_slot.submission
    event = submission.event
    # use_feedback is False by default
    client.force_login(user)
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = client.post(
        url,
        {
            'talk': submission.code,
            'review': 'Great talk!',
            'is_public': True,
        },
    )
    assert response.status_code == 403
    assert response.data['detail'] == 'Feedback is not enabled for this event.'
    with scope(event=event):
        assert Feedback.objects.count() == 0
