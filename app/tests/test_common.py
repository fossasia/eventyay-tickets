"""
Tests for common pages and utilities (redirects, CSP reporting, etc).
"""
import pytest


@pytest.mark.django_db
class TestCommonPages:
    """Test common utility endpoints."""

    def test_redirect_endpoint_exists(self, client):
        """Test redirect utility endpoint."""
        response = client.get('/redirect/')
        # Should handle redirect requests
        assert response.status_code in [200, 302, 400]

    def test_csp_report_endpoint(self, client):
        """Test CSP report endpoint accepts POST."""
        response = client.post('/csp_report/', data='{}', content_type='application/json')
        # Should accept CSP reports
        assert response.status_code in [200, 204]

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint (may require auth)."""
        response = client.get('/metrics')
        # May require auth or return metrics
        assert response.status_code in [200, 401, 403]


@pytest.mark.django_db
class TestStaticPages:
    """Test static content and assets."""

    def test_static_url_pattern(self, client):
        """Test that static URL pattern is configured."""
        # Just verify the static URL doesn't 500
        response = client.get('/static/')
        # May 404 but shouldn't crash
        assert response.status_code in [200, 301, 302, 404]

    def test_media_url_pattern(self, client):
        """Test that media URL pattern is configured."""
        response = client.get('/media/')
        # May 404 but shouldn't crash
        assert response.status_code in [200, 301, 302, 404]
