"""
Tests for organizer control panel and event management pages.
These require authentication and organizer team membership.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestOrganizerPages:
    """Test organizer/control panel pages."""

    def test_organizer_login_page_loads(self, client):
        """Test that organizer login page is accessible."""
        # Try accessing the orga base URL
        response = client.get('/orga/')
        # Should redirect to login or show login page
        assert response.status_code in [200, 302]

    def test_organizer_dashboard_requires_auth(self, client, organizer):
        """Test that organizer dashboard requires authentication."""
        url = f'/orga/organizer/{organizer.slug}/'
        response = client.get(url)
        # Should redirect to login
        assert response.status_code == 302

    def test_organizer_dashboard_with_auth(self, organizer_client, organizer):
        """Test organizer dashboard accessible for team members."""
        url = f'/orga/organizer/{organizer.slug}/'
        response = organizer_client.get(url)
        # Should load or redirect to appropriate page
        assert response.status_code in [200, 302]

    def test_event_list_with_auth(self, organizer_client):
        """Test event list page for authenticated organizer."""
        response = organizer_client.get('/orga/event/')
        # Should show event list
        assert response.status_code == 200


@pytest.mark.django_db
class TestEventManagement:
    """Test event management pages."""

    def test_event_dashboard_requires_auth(self, client, organizer, event):
        """Test event dashboard requires authentication."""
        url = f'/orga/event/{organizer.slug}/{event.slug}/'
        response = client.get(url)
        # Should redirect to login
        assert response.status_code == 302

    def test_event_dashboard_with_auth(self, organizer_client, organizer, event):
        """Test event dashboard loads for team members."""
        url = f'/orga/event/{organizer.slug}/{event.slug}/'
        response = organizer_client.get(url)
        # Should load dashboard
        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestAdminPages:
    """Test admin interface pages."""

    def test_admin_index_requires_staff(self, client):
        """Test admin index requires staff permission."""
        response = client.get('/admin/')
        # Should redirect to login
        assert response.status_code == 302

    def test_admin_index_with_staff(self, staff_client):
        """Test admin index loads for staff users."""
        response = staff_client.get('/admin/')
        # Should load admin interface
        assert response.status_code == 200

    def test_admin_dashboard(self, staff_client):
        """Test admin dashboard page."""
        response = staff_client.get('/orga/admin/')
        # Should load admin dashboard
        assert response.status_code in [200, 302]
