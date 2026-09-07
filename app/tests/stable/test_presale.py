"""
Tests for public presale/event pages (agenda, schedule, speakers).
These pages should be accessible without authentication.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from eventyay.base.models import Event


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

    def test_upcoming_events_page_loads(self, client):
        """Test that the upcoming events page loads at the new URL."""
        response = client.get('/upcoming/')
        assert response.status_code == 200

    def test_upcoming_events_old_url_redirects(self, client):
        """Test that old /all-events/upcoming/ redirects to /upcoming/."""
        response = client.get('/all-events/upcoming/')
        assert response.status_code == 301
        assert response['Location'] == '/upcoming/'

    def test_past_events_page_loads(self, client):
        """Test that the past events page loads at the new URL."""
        response = client.get('/past/')
        assert response.status_code == 200

    def test_past_events_old_url_redirects(self, client):
        """Test that old /all-events/past/ redirects to /past/."""
        response = client.get('/all-events/past/')
        assert response.status_code == 301
        assert response['Location'] == '/past/'

    def test_past_events_excludes_non_public_events(self, client, organizer):
        """Events with 'Show in lists' disabled must not appear on /past/."""
        now = timezone.now()
        common_kwargs = {
            'organizer': organizer,
            'live': True,
            'startpage_visible': True,
            'date_from': now - timedelta(days=30),
            'date_to': now - timedelta(days=29),
            'currency': 'USD',
            'locale': 'en',
            'email': 'test@example.com',
        }
        Event.objects.create(name='Public Past Event', slug='public-past', is_public=True, **common_kwargs)
        Event.objects.create(name='Hidden Past Event', slug='hidden-past', is_public=False, **common_kwargs)

        response = client.get('/past/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Public Past Event' in content
        assert 'Hidden Past Event' not in content

    def test_followed_events_page_redirects_unauthenticated(self, client):
        """Test that followed events page redirects anonymous users to login."""
        response = client.get('/followed-events/')
        assert response.status_code == 302

    def test_followed_events_page_loads_authenticated(self, client, user):
        """Test that followed events page loads for authenticated users."""
        client.force_login(user)
        response = client.get('/followed-events/')
        assert response.status_code == 200


@pytest.mark.django_db
class TestEventPages:
    """Test event-specific public pages."""

    def test_event_landing_page(self, client, organizer, event):
        """Test that event landing page loads for valid event."""
        url = f'/{organizer.slug}/{event.slug}/'
        response = client.get(url)
        # Should return 200 for a valid public event or redirect
        assert response.status_code in [200, 301, 302]

    def test_invalid_organizer_slug(self, client, event):
        """Test that an invalid organizer slug returns 404."""
        url = f'/nonexistent-organizer/{event.slug}/'
        response = client.get(url)
        assert response.status_code == 404

    def test_invalid_event_slug(self, client, organizer):
        """Test that an invalid event slug returns 404."""
        url = f'/{organizer.slug}/nonexistent-event/'
        response = client.get(url)
        assert response.status_code == 404

    def test_invalid_organizer_and_event_slug(self, client):
        """Test that both invalid organizer and event slugs return 404."""
        url = '/nonexistent-organizer/nonexistent-event/'
        response = client.get(url)
        assert response.status_code == 404

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
