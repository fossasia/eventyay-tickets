from urllib.parse import urlparse

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def env(event):
    settings.SITE_URL = "http://example.com:444"
    settings.SITE_NETLOC = urlparse(settings.SITE_URL).netloc


@pytest.mark.django_db
def test_event_on_unknown_domain(event, client):
    r = client.get("/{event.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 404, r.content.decode()


@pytest.mark.django_db
def test_orga_event_on_unknown_domain(event, client):
    r = client.get("/orga/event/{event.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 404, r.content.decode()
