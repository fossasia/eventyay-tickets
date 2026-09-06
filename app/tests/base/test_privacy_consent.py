import json

import pytest

from eventyay.base.models.privacy import ConsentCategory, ConsentProvider, ThirdPartyService
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.templatetags.privacy_consent import consent_config, external_cmp_script


@pytest.fixture
def gs():
    obj = GlobalSettingsObject()
    obj.settings.set('privacy_consent_provider', ConsentProvider.KLARO)
    obj.settings.set('privacy_cookie_policy_url', 'https://example.org/cookies')
    return obj


@pytest.mark.django_db
def test_consent_disabled_renders_nothing():
    gso = GlobalSettingsObject()
    gso.settings.set('privacy_consent_provider', ConsentProvider.DISABLED)
    assert consent_config() is None


@pytest.mark.django_db
def test_optional_categories_are_off_by_default(gs):
    config = json.loads(consent_config())
    # Only the always-on category is present until an admin enables more.
    assert config['purposes'] == [ConsentCategory.NECESSARY.value]
    assert config['default'] is False


@pytest.mark.django_db
def test_enabled_category_is_advertised(gs):
    gs.settings.set('privacy_category_analytics_enabled', True)
    config = json.loads(consent_config())
    assert ConsentCategory.ANALYTICS.value in config['purposes']
    assert ConsentCategory.MARKETING.value not in config['purposes']


@pytest.mark.django_db
def test_optional_service_hidden_until_category_enabled(gs):
    ThirdPartyService.objects.create(
        name='google-analytics',
        title='Google Analytics',
        category=ConsentCategory.ANALYTICS,
    )
    assert json.loads(consent_config())['services'] == []

    gs.settings.set('privacy_category_analytics_enabled', True)
    services = json.loads(consent_config())['services']
    assert [s['name'] for s in services] == ['google-analytics']
    # Must not be preselected.
    assert services[0]['default'] is False
    assert services[0]['required'] is False


@pytest.mark.django_db
def test_necessary_service_is_always_active(gs):
    ThirdPartyService.objects.create(
        name='stripe', title='Stripe', category=ConsentCategory.NECESSARY
    )
    service = json.loads(consent_config())['services'][0]
    assert service['required'] is True
    assert service['default'] is True


@pytest.mark.django_db
def test_disabled_service_is_not_published(gs):
    gs.settings.set('privacy_category_analytics_enabled', True)
    ThirdPartyService.objects.create(
        name='matomo',
        title='Matomo',
        category=ConsentCategory.ANALYTICS,
        enabled=False,
    )
    assert json.loads(consent_config())['services'] == []


@pytest.mark.django_db
def test_klaro_and_external_cmp_are_mutually_exclusive(gs):
    gs.settings.set('privacy_consent_provider', ConsentProvider.EXTERNAL)
    gs.settings.set('privacy_cmp_script_url', 'https://cdn.example.org/cmp.js')

    # Built-in banner must not render while an external CMP is selected.
    assert consent_config() is None
    assert external_cmp_script() == 'https://cdn.example.org/cmp.js'


@pytest.mark.django_db
def test_external_script_not_emitted_in_klaro_mode(gs):
    gs.settings.set('privacy_cmp_script_url', 'https://cdn.example.org/cmp.js')
    assert external_cmp_script() == ''
