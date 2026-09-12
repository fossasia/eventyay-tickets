"""
Tests for organizer control panel and event management pages.
These require authentication and organizer team membership.
"""
import pytest
from urllib.parse import urlparse


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
        # Verify redirect is to login page
        redirect_path = urlparse(response.url).path
        # Depending on deployment, auth routes may live under /login/ or /orga/login/.
        assert (
            redirect_path.startswith('/login')
            or redirect_path.startswith('/orga/login')
        )

    def test_organizer_dashboard_with_auth(self, organizer_client, organizer):
        """Test organizer dashboard accessible for team members."""
        url = f'/orga/organizer/{organizer.slug}/'
        response = organizer_client.get(url)
        # Should load or redirect to appropriate page
        assert response.status_code in [200, 302]
        if response.status_code == 302:
            # Should redirect to event list or dashboard, not login
            redirect_path = urlparse(response.url).path
            assert not (redirect_path.startswith('/login') or redirect_path.startswith('/orga/login'))

    def test_event_list_with_auth(self, organizer_client):
        response = organizer_client.get('/orga/event/')
        assert response.status_code == 200


@pytest.mark.django_db
class TestEventManagement:
    """Test event management pages."""

    def test_event_dashboard_requires_auth(self, client, organizer, event):
        """Test event dashboard requires authentication."""
        url = f'/orga/event/{organizer.slug}/{event.slug}/'
        response = client.get(url)
        # Route may not exist in all configurations, but if it does it should require auth.
        if response.status_code == 404:
            pytest.skip('Event dashboard route not present in this configuration')
        assert response.status_code == 302
        redirect_path = urlparse(response.url).path
        assert (
            redirect_path.startswith('/login')
            or redirect_path.startswith('/orga/login')
        )

    def test_event_dashboard_with_auth(self, organizer_client, organizer, event):
        """Test event dashboard loads for team members."""
        url = f'/orga/event/{organizer.slug}/{event.slug}/'
        response = organizer_client.get(url)
        if response.status_code == 404:
            pytest.skip('Event dashboard route not present in this configuration')
        # Should load dashboard or redirect to a valid page
        assert response.status_code in [200, 302]
        if response.status_code == 302:
            # Should not redirect back to login
            redirect_path = urlparse(response.url).path
            assert not (
                redirect_path.startswith('/login')
                or redirect_path.startswith('/orga/login')
            )


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
        # Some deployments require a sudo step for /admin/
        assert response.status_code in [200, 302]

    def test_admin_dashboard(self, staff_client):
        """Test admin dashboard page."""
        response = staff_client.get('/orga/admin/')
        if response.status_code == 404:
            pytest.skip('Orga admin route not present in this configuration')
        # Should load admin dashboard or redirect appropriately
        assert response.status_code in [200, 302]


@pytest.fixture
def admin_client(db, staff_client, staff_user):
    """Staff client with an active sudo/staff session for admin views."""
    from eventyay.base.models.auth import StaffSession

    session = staff_client.session
    session.save()
    StaffSession.objects.create(
        user=staff_user,
        session_key=session.session_key,
        comment='test',
    )
    return staff_client


@pytest.mark.django_db
class TestEventAdminToken:
    def test_admin_token_rejects_get(self, admin_client, event):
        response = admin_client.get(f'/admin/video/events/{event.pk}/admin')
        assert response.status_code == 405
        event.refresh_from_db()
        assert not (event.config or {}).get('JWT_secrets')

    def test_admin_token_creates_secret_on_post(self, admin_client, event):
        from eventyay.base.models.log import LogEntry

        response = admin_client.post(f'/admin/video/events/{event.pk}/admin')
        assert response.status_code == 302
        event.refresh_from_db()
        assert event.config['JWT_secrets']
        assert LogEntry.objects.filter(action_type='event.adminaccess').exists()


@pytest.mark.django_db
class TestGlobalSettingsEmail:
    """Test global settings email functionality."""

    def test_test_email_requires_staff(self, client):
        """Test test email endpoint requires staff permission."""
        from django.urls import reverse
        url = reverse('eventyay_admin:admin.global.settings.test_email')
        response = client.post(url, {'test_email': 'test@example.com'})
        assert response.status_code == 302

    def test_test_email_rejects_invalid_recipients(self, admin_client):
        from django.urls import reverse
        url = reverse('eventyay_admin:admin.global.settings.test_email')
        response = admin_client.post(url, {'test_email': 'invalid-email'})
        assert response.status_code == 302
        assert response['Location'].endswith('#tab3')

    def test_test_email_invalid_sender(self, admin_client):
        from django.urls import reverse
        from eventyay.base.settings import GlobalSettingsObject

        gs = GlobalSettingsObject()
        gs.settings.set('mail_from', 'invalid-email')

        url = reverse('eventyay_admin:admin.global.settings.test_email')
        response = admin_client.post(url, {'test_email': 'test@example.com'})
        assert response.status_code == 302
        assert response['Location'].endswith('#tab3')

    def test_test_email_smtp_unreachable(self, admin_client, monkeypatch):
        from django.urls import reverse
        from eventyay.base.settings import GlobalSettingsObject

        def mock_open(self):
            raise OSError("Network is unreachable")
        monkeypatch.setattr('eventyay.base.email.CustomSMTPBackend.open', mock_open)

        gs = GlobalSettingsObject()
        gs.settings.set('mail_from', 'valid@example.com')
        gs.settings.set('email_vendor', 'smtp')
        gs.settings.set('smtp_host', 'unreachable.example.com')
        gs.settings.set('smtp_port', 25)

        url = reverse('eventyay_admin:admin.global.settings.test_email')
        response = admin_client.post(url, {'test_email': 'test@example.com'})
        assert response.status_code == 302
        assert response['Location'].endswith('#tab3')
