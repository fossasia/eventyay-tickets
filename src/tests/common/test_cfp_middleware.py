from urllib.parse import urlparse

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def env(event):
    settings.SITE_URL = "http://example.com"
    settings.SITE_NETLOC = urlparse(settings.SITE_URL).netloc


@pytest.fixture
def event_on_foobar(event):
    event.custom_domain = "https://foobar"
    event.save()
    return event


@pytest.fixture
def event_on_custom_port(event):
    event.custom_domain = "https://foobar:8000"
    event.save()
    return event


@pytest.mark.django_db
def test_event_on_unknown_domain(event, client):
    r = client.get("/{event.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 404


@pytest.mark.django_db
def test_orga_on_unknown_domain(event, client):
    r = client.get("/orga/login/", HTTP_HOST="foobar")
    assert r.status_code == 302


@pytest.mark.django_db
def test_event_on_custom_domain(event_on_foobar, client):
    r = client.get(f"/{event_on_foobar.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 200


@pytest.mark.django_db
def test_event_on_custom_port(event_on_custom_port, client):
    r = client.get(f"/{event_on_custom_port.slug}/", HTTP_HOST="foobar:8000")
    assert r.status_code == 200


@pytest.mark.django_db
def test_event_on_custom_domain_in_orga_area(event_on_foobar, client):
    r = client.get(f"/orga/event/{event_on_foobar.slug}/", HTTP_HOST="foobar")
    assert r.status_code == 302
    assert r["Location"] == f"http://example.com/orga/event/{event_on_foobar.slug}/"


@pytest.mark.django_db
def test_event_on_custom_port_in_orga_area(event_on_custom_port, client):
    r = client.get(f"/orga/event/{event_on_custom_port.slug}/", HTTP_HOST="foobar:8000")
    assert r.status_code == 302
    assert (
        r["Location"] == f"http://example.com/orga/event/{event_on_custom_port.slug}/"
    )


@pytest.mark.django_db
def test_event_with_custom_domain_on_main_domain(event_on_foobar, client):
    """redirect from common domain to custom domain."""
    r = client.get(f"/{event_on_foobar.slug}/", HTTP_HOST="example.com")
    assert r.status_code == 302
    assert r["Location"] == f"https://foobar/{event_on_foobar.slug}/"
    assert r["Access-Control-Allow-Origin"] == "*"


@pytest.mark.django_db
def test_event_with_custom_port_on_main_domain(event_on_custom_port, client):
    """redirect from common domain to custom domain."""
    r = client.get(f"/{event_on_custom_port.slug}/", HTTP_HOST="example.com")
    assert r.status_code == 302
    assert r["Location"] == f"https://foobar:8000/{event_on_custom_port.slug}/"


@pytest.mark.django_db
def test_unknown_event_on_custom_domain(event_on_foobar, client):
    r = client.get("/1234/", HTTP_HOST="foobar")
    assert r.status_code == 404


@pytest.mark.django_db
def test_with_forwarded_host(event_on_foobar, client):
    settings.USE_X_FORWARDED_HOST = True
    r = client.get(f"/{event_on_foobar.slug}/", HTTP_X_FORWARDED_HOST="foobar")
    assert r.status_code == 200


settings.USE_X_FORWARDED_HOST = False
