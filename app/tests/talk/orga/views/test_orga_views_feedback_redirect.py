import pytest
from django_scopes import scope

from eventyay.base.models.feedback import Feedback

EXTERNAL_NEXT = 'https://evil.example.com/phish'


@pytest.mark.django_db
def test_feedback_bulk_empty_open_redirect_is_blocked(orga_client, event):
    """Empty-selection branch: an external `next` must fall back to the feedback page."""
    url = event.orga_urls.feedback + 'bulk/?next=' + EXTERNAL_NEXT
    response = orga_client.post(url, {})
    assert response.status_code == 302
    assert response['Location'] == event.orga_urls.feedback


@pytest.mark.django_db
def test_feedback_bulk_empty_safe_next_is_honored(orga_client, event):
    """Empty-selection branch: a safe internal `next` is still honored."""
    safe = event.orga_urls.feedback
    url = event.orga_urls.feedback + 'bulk/?next=' + safe
    response = orga_client.post(url, {})
    assert response.status_code == 302
    assert response['Location'] == safe


@pytest.mark.django_db
def test_feedback_bulk_completion_open_redirect_is_blocked(orga_client, event):
    """Completion branch (non-empty selection): external `next` falls back."""
    url = event.orga_urls.feedback + 'bulk/?next=' + EXTERNAL_NEXT
    response = orga_client.post(url, {'feedback_ids': ['999999'], 'action': 'approve'})
    assert response.status_code == 302
    assert response['Location'] == event.orga_urls.feedback


@pytest.mark.django_db
def test_feedback_update_status_get_open_redirect_is_blocked(orga_client, event, submission):
    """FeedbackUpdateStatus.get: external `next` falls back to the feedback page."""
    with scope(event=event):
        feedback = Feedback.objects.create(talk=submission, review='ok')
    url = event.orga_urls.feedback + f'{feedback.pk}/action/?action=noop&next=' + EXTERNAL_NEXT
    response = orga_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == event.orga_urls.feedback
