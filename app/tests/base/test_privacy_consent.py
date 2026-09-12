import json
from pathlib import Path

import pytest
from django.conf import settings

from eventyay.base.models.privacy import ConsentCategory, ConsentProvider, ThirdPartyService
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.templatetags.privacy_consent import (
    build_consent_config,
    consent_config,
    consent_embed,
    external_cmp_script,
)


@pytest.fixture
def gs():
    """gs method."""
    obj = GlobalSettingsObject()
    obj.settings.set('privacy_consent_provider', ConsentProvider.KLARO)
    obj.settings.set('privacy_cookie_policy_url', 'https://example.org/cookies')
    return obj


@pytest.mark.django_db
def test_consent_disabled_renders_nothing():
    """Consent disabled renders nothing."""
    gso = GlobalSettingsObject()
    gso.settings.set('privacy_consent_provider', ConsentProvider.DISABLED)
    assert build_consent_config() is None


@pytest.mark.django_db
def test_optional_categories_are_off_by_default(gs):
    """Optional categories are off by default."""
    config = build_consent_config()
    # Only the always-on category is present until an admin enables more.
    assert config['purposes'] == [ConsentCategory.NECESSARY.value]
    assert config['default'] is False


@pytest.mark.django_db
def test_enabled_category_is_advertised(gs):
    """Enabled category is advertised."""
    gs.settings.set('privacy_category_analytics_enabled', True)
    config = build_consent_config()
    assert ConsentCategory.ANALYTICS.value in config['purposes']
    assert ConsentCategory.MARKETING.value not in config['purposes']


@pytest.mark.django_db
def test_optional_service_hidden_until_category_enabled(gs):
    """Optional service hidden until category enabled."""
    ThirdPartyService.objects.create(
        name='google-analytics',
        title='Google Analytics',
        category=ConsentCategory.ANALYTICS,
    )
    assert build_consent_config()['services'] == []

    gs.settings.set('privacy_category_analytics_enabled', True)
    services = build_consent_config()['services']
    assert [s['name'] for s in services] == ['google-analytics']
    # Must not be preselected.
    assert services[0]['default'] is False
    assert services[0]['required'] is False


@pytest.mark.django_db
def test_necessary_service_is_always_active(gs):
    """Necessary service is always active."""
    ThirdPartyService.objects.create(name='stripe', title='Stripe', category=ConsentCategory.NECESSARY)
    service = build_consent_config()['services'][0]
    assert service['required'] is True
    assert service['default'] is True


@pytest.mark.django_db
def test_disabled_service_is_not_published(gs):
    """Disabled service is not published."""
    gs.settings.set('privacy_category_analytics_enabled', True)
    ThirdPartyService.objects.create(
        name='matomo',
        title='Matomo',
        category=ConsentCategory.ANALYTICS,
        enabled=False,
    )
    assert build_consent_config()['services'] == []


@pytest.mark.django_db
def test_klaro_and_external_cmp_are_mutually_exclusive(gs):
    """Klaro and external cmp are mutually exclusive."""
    gs.settings.set('privacy_consent_provider', ConsentProvider.EXTERNAL)
    gs.settings.set('privacy_cmp_script_url', 'https://cdn.example.org/cmp.js')

    # Built-in banner must not render while an external CMP is selected.
    assert build_consent_config() is None
    assert external_cmp_script() == 'https://cdn.example.org/cmp.js'


@pytest.mark.django_db
def test_external_script_not_emitted_in_klaro_mode(gs):
    """External script not emitted in klaro mode."""
    gs.settings.set('privacy_cmp_script_url', 'https://cdn.example.org/cmp.js')
    assert external_cmp_script() == ''


@pytest.mark.django_db
def test_service_title_cannot_break_out_of_the_config_script(gs):
    """A service title containing `</script>` must not close the JSON element."""
    gs.settings.set('privacy_category_analytics_enabled', True)
    ThirdPartyService.objects.create(
        name='hostile',
        title='</script><script>window.pwned = true;</script>',
        purpose='Closes the tag too: </script>',
        category=ConsentCategory.ANALYTICS,
    )

    rendered = consent_config()

    payload = rendered[rendered.index('>') + 1 : rendered.rindex('</script>')]

    # The wrapper's own closing tag must be the only one on the page.
    assert rendered.count('</script>') == 1
    # Inside the payload, dangerous characters survive only as escapes.
    assert '<' not in payload
    assert '>' not in payload
    assert '\\u003C' in payload
    service = json.loads(payload)['services'][0]
    # Escaping must survive the round trip, not mangle the admin's text.
    assert service['title'] == '</script><script>window.pwned = true;</script>'


@pytest.mark.django_db
def test_embed_is_blocked_only_under_the_builtin_banner(gs):
    """Embed is blocked only under the builtin banner."""
    context = consent_embed('youtube', 'https://example.org/v', 'Talk recording')
    assert context['blocked'] is True


@pytest.mark.django_db
@pytest.mark.parametrize('provider', [ConsentProvider.DISABLED, ConsentProvider.EXTERNAL])
def test_embed_renders_directly_without_the_builtin_banner(gs, provider):
    """
    Nothing swaps placeholders in under these providers, so a placeholder here
    would make the embed permanently unreachable.
    """
    gs.settings.set('privacy_consent_provider', provider)
    context = consent_embed('youtube', 'https://example.org/v', 'Talk recording')
    assert context['blocked'] is False
    assert context['src'] == 'https://example.org/v'


@pytest.mark.django_db
def test_configured_cookie_names_reach_the_payload(gs):
    """Klaro needs the cookie names to clear them when consent is withdrawn."""
    gs.settings.set('privacy_category_analytics_enabled', True)
    ThirdPartyService.objects.create(
        name='matomo',
        title='Matomo',
        category=ConsentCategory.ANALYTICS,
        cookie_names='_pk_id\n  _pk_ses  \n\n',
    )

    service = build_consent_config()['services'][0]

    # Blank lines dropped and surrounding whitespace trimmed.
    assert service['cookies'] == ['_pk_id', '_pk_ses']


@pytest.mark.django_db
def test_service_without_cookie_names_serializes_empty_list(gs):
    """Service without cookie names serializes empty list."""
    gs.settings.set('privacy_category_analytics_enabled', True)
    ThirdPartyService.objects.create(name='plausible', title='Plausible', category=ConsentCategory.ANALYTICS)

    assert build_consent_config()['services'][0]['cookies'] == []


def test_footer_link_and_consent_layer_ship_together():
    """
    The footer's "Privacy settings" link is inert unless the consent layer is
    loaded, so the include lives in the same shared partial as the link.
    """
    partial = Path(settings.BASE_DIR) / 'common/templates/common/includes/core_footer.html'
    footer = partial.read_text(encoding='utf-8')

    assert 'data-privacy-settings' in footer
    assert 'eventyay/privacy/consent.html' in footer
