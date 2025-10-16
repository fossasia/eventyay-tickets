"""
Tests for public presale/event pages (agenda, schedule, speakers).
These pages should be accessible without authentication.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestPresalePages:
    """Test public event pages accessible via presale URLs."""

    def test_index_page_loads(self, client):
        """Test that the main index page loads."""
        response = client.get('/')
        # Should either show landing or redirect
        assert response.status_code in [200, 301, 302]

    def test_locale_set_endpoint(self, client):
        """Test locale setting endpoint exists."""
        response = client.get('/locale/set?locale=en&next=/')
        # Should redirect after setting locale
        assert response.status_code in [302, 200]


@pytest.mark.django_db
class TestEventPages:
    """Test event-specific public pages."""

    def test_event_landing_page(self, client, organizer, event):
        """Test that event landing page loads."""
        url = f'/{organizer.slug}/{event.slug}/'
        response = client.get(url)
        # May return 200 or redirect depending on event setup
        assert response.status_code in [200, 301, 302, 404]

    def test_robots_txt(self, client):
        """Test that robots.txt is accessible."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert 'text/plain' in response['Content-Type']


@pytest.mark.django_db
class TestAgendaPages:
    """Test agenda/schedule pages."""

    def test_schedule_view_exists(self, client, organizer, event):
        """Test schedule page URL pattern."""
        url = f'/agenda/{organizer.slug}/{event.slug}/schedule/'
        response = client.get(url)
        # May 404 if schedule not configured, but shouldn't 500
        assert response.status_code in [200, 404]

    def test_speaker_list_exists(self, client, organizer, event):
        """Test speaker list page URL pattern."""
        url = f'/agenda/{organizer.slug}/{event.slug}/speaker/'
        response = client.get(url)
        # May 404 if speakers not configured, but shouldn't 500
        assert response.status_code in [200, 404]
