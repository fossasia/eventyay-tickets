"""
Tests for health and status endpoints.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHealthcheck:
    """Test the /healthcheck/ endpoint."""

    def test_healthcheck_returns_200(self, client):
        """Healthcheck should return 200 OK when services are available."""
        response = client.get('/healthcheck/')
        assert response.status_code == 200

    def test_healthcheck_empty_body(self, client):
        """Healthcheck returns empty body on success."""
        response = client.get('/healthcheck/')
        assert response.content == b''

    def test_healthcheck_content_type(self, client):
        """Healthcheck returns text/html content type."""
        response = client.get('/healthcheck/')
        assert 'text/html' in response['Content-Type']
