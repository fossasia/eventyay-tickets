from urllib.parse import urlparse

import pytest
from django.conf import settings
from django.test.utils import override_settings


@pytest.fixture(autouse=True)
def env(event):
    settings.SITE_URL = 'http://example.com'
    settings.SITE_NETLOC = urlparse(settings.SITE_URL).netloc


@pytest.fixture
def event_on_foobar(event):
    event.settings.set('custom_domain', 'https://foobar')
    return event


@pytest.mark.django_db
def test_unknown_domain(event, client):
    r = client.get('/orga/login/', HTTP_HOST='foobar')
    assert r.status_code == 400


@pytest.mark.django_db
def test_event_on_custom_domain(event_on_foobar, client):
    r = client.get(f'/{event_on_foobar.slug}/', HTTP_HOST='foobar')
    assert r.status_code == 200


@pytest.mark.django_db
def test_event_on_custom_domain_in_orga_area(event_on_foobar, client):
    r = client.get(f'/orga/event/{event_on_foobar.slug}/', HTTP_HOST='foobar')
    assert r.status_code == 302
    assert r['Location'] == f'http://example.com/orga/event/{event_on_foobar.slug}/'


@pytest.mark.django_db
def test_event_with_custom_domain_on_main_domain(event_on_foobar, client):
    """ redirect from common domain to custom domain """
    r = client.get(f'/{event_on_foobar.slug}/', HTTP_HOST='example.com')
    assert r.status_code == 302
    assert r['Location'] == f'https://foobar/{event_on_foobar.slug}/'


@pytest.mark.django_db
def test_unknown_event_on_custom_domain(event_on_foobar, client):
    r = client.get('/1234/', HTTP_HOST='foobar')
    assert r.status_code == 404


@pytest.mark.django_db
def test_cookie_domain_on_custom_domain(event_on_foobar, client):
    r = client.get(f'/{event_on_foobar.slug}/login/', HTTP_HOST='foobar')
    assert r.status_code == 200
    assert r.client.cookies['pretalx_csrftoken']['domain'] == ''
    assert r.client.cookies['pretalx_session']['domain'] == ''


@pytest.mark.django_db
def test_cookie_domain_on_main_domain(event, client):
    with override_settings(SESSION_COOKIE_DOMAIN='example.com'):
        r = client.get(f'/{event.slug}/login/', HTTP_HOST='example.com')
        assert r.status_code == 200
        assert r.client.cookies['pretalx_csrftoken']['domain'] == 'example.com'
        assert r.client.cookies['pretalx_session']['domain'] == 'example.com'


@pytest.mark.django_db
def test_with_forwarded_host(event_on_foobar, client):
    settings.USE_X_FORWARDED_HOST = True
    r = client.get(f'/{event_on_foobar.slug}/', HTTP_X_FORWARDED_HOST='foobar')
    assert r.status_code == 200


settings.USE_X_FORWARDED_HOST = False
