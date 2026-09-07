import pytest


@pytest.mark.django_db
def test_feedback_bulk_open_redirect_is_blocked(orga_client, event):
    """An external `next` URL must not be used as a redirect target (CWE-601)."""
    url = event.orga_urls.feedback + 'bulk/?next=https://evil.example.com/phish'
    response = orga_client.post(url, {})
    assert response.status_code == 302
    assert 'evil.example.com' not in response['Location']


@pytest.mark.django_db
def test_feedback_bulk_safe_next_is_honored(orga_client, event):
    """A safe, internal `next` URL is still honored."""
    safe = event.orga_urls.feedback
    url = event.orga_urls.feedback + 'bulk/?next=' + safe
    response = orga_client.post(url, {})
    assert response.status_code == 302
    assert response['Location'] == safe
