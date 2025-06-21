import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(
    SITE_URL="http://example.com:444",
    SITE_NETLOC="example.com",
)
def test_event_on_unknown_domain(event, client):
    r = client.get("/{event.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 404, r.content.decode()


@pytest.mark.django_db
@override_settings(
    SITE_URL="http://example.com:444",
    SITE_NETLOC="example.com",
)
def test_orga_event_on_unknown_domain(event, client):
    r = client.get("/orga/event/{event.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 404, r.content.decode()
