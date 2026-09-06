import json

from django import template
from django.utils.safestring import mark_safe

from eventyay.base.models.privacy import ConsentCategory, ConsentProvider, ThirdPartyService
from eventyay.base.settings import GlobalSettingsObject


register = template.Library()


def _enabled_categories(settings):
    return [
        category.value
        for category in ConsentCategory.optional()
        if settings.get(f'privacy_category_{category.value}_enabled', as_type=bool)
    ]


@register.simple_tag
def consent_config():
    """
    Build the Klaro configuration from admin settings and the service registry.

    Returns ``None`` when consent is disabled so templates can skip rendering
    the consent layer entirely.
    """
    gs = GlobalSettingsObject()
    settings = gs.settings
    provider = settings.get('privacy_consent_provider') or ConsentProvider.DISABLED

    if provider != ConsentProvider.KLARO:
        return None

    enabled = _enabled_categories(settings)
    services = ThirdPartyService.objects.filter(enabled=True)

    config = {
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
            service.serialize_public()
            for service in services
            if service.required or service.category in enabled
        ],
    }
    return mark_safe(json.dumps(config))


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

    The iframe is never emitted server-side; the placeholder is swapped for it
    in the browser once the visitor accepts the relevant category.
    """
    return {'service': service, 'src': src, 'title': title}
