from django import template
from django.utils.html import json_script

from eventyay.base.models.privacy import (
    ConsentCategory,
    ConsentProvider,
    ThirdPartyService,
    enabled_consent_categories,
)
from eventyay.base.settings import GlobalSettingsObject


register = template.Library()

CONFIG_ELEMENT_ID = 'klaro-config'


def build_consent_config():
    """
    Build the Klaro configuration from admin settings and the service registry.

    Returns ``None`` when the built-in banner is not the active provider, so
    templates can skip rendering the consent layer entirely.
    """
    gs = GlobalSettingsObject()
    settings = gs.settings
    provider = settings.get('privacy_consent_provider') or ConsentProvider.DISABLED

    if provider != ConsentProvider.KLARO:
        return None

    enabled = enabled_consent_categories(settings)
    services = ThirdPartyService.objects.filter(enabled=True)

    return {
        'elementID': 'klaro',
        'storageMethod': 'cookie',
        'cookieName': 'eventyay_consent',
        'privacyPolicy': settings.get('privacy_policy_url') or '',
        'cookiePolicy': settings.get('privacy_cookie_policy_url') or '',
        # Opt-in: nothing optional runs until the visitor accepts it.
        'default': False,
        'mustConsent': False,
        'acceptAll': True,
        'hideDeclineAll': False,
        'purposes': [ConsentCategory.NECESSARY.value] + enabled,
        'services': [
            service.serialize_public() for service in services if service.required or service.category in enabled
        ],
    }


@register.simple_tag
def consent_config():
    """
    Render the Klaro configuration as a JSON ``<script>`` element.

    Service titles and purposes are administrator-supplied, so the payload is
    written with ``json_script``: it escapes ``<``, ``>`` and ``&`` as unicode
    escapes, which keeps a value containing ``</script>`` from closing the
    element early and injecting markup into every public page.
    """
    config = build_consent_config()
    if config is None:
        return None
    return json_script(config, CONFIG_ELEMENT_ID)


@register.simple_tag
def consent_provider():
    gs = GlobalSettingsObject()
    return gs.settings.get('privacy_consent_provider') or ConsentProvider.DISABLED


@register.simple_tag
def external_cmp_script():
    gs = GlobalSettingsObject()
    if (gs.settings.get('privacy_consent_provider') or '') != ConsentProvider.EXTERNAL:
        return ''
    return gs.settings.get('privacy_cmp_script_url') or ''


@register.inclusion_tag('eventyay/privacy/embed_placeholder.html')
def consent_embed(service, src, title=''):
    """
    Render a third-party embed behind contextual consent.

    Only the built-in banner can unblock a placeholder, because
    ``revealConsentedEmbeds`` ships with the Klaro bootstrap. Under the other
    providers the embed is rendered directly instead: with consent disabled
    there is nothing to gate on, and an external CMP does its own blocking of
    third-party frames. Emitting a placeholder in those modes would leave the
    content permanently unreachable.
    """
    gs = GlobalSettingsObject()
    provider = gs.settings.get('privacy_consent_provider') or ConsentProvider.DISABLED
    return {
        'service': service,
        'src': src,
        'title': title,
        'blocked': provider == ConsentProvider.KLARO,
    }
