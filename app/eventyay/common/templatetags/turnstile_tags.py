from django import template
from django.utils.html import format_html

from eventyay.base.services.turnstile import (
    get_turnstile_settings,
    is_turnstile_enabled_for_action,
)


register = template.Library()


@register.simple_tag(takes_context=True)
def turnstile_widget(context, action='login', theme='auto', size='normal'):
    """
    Renders the Cloudflare Turnstile widget if enabled for the given action.
    Usage:
        {% load turnstile_tags %}
        {% turnstile_widget 'login' %}
    """
    request = context.get('request')
    if not is_turnstile_enabled_for_action(action, request):
        return ''

    cfg = get_turnstile_settings()
    site_key = cfg.get('site_key', '')
    if not site_key:
        return ''

    return format_html(
        '<div class="cf-turnstile form-group" '
        'data-sitekey="{}" '
        'data-action="{}" '
        'data-theme="{}" '
        'data-size="{}"></div>',
        site_key,
        action,
        theme,
        size,
    )


@register.simple_tag(takes_context=True)
def turnstile_script(context, action=None):
    """
    Renders the Cloudflare Turnstile script tag.
    If action is given, only renders if Turnstile is enabled for that action.
    """
    request = context.get('request')
    if action and not is_turnstile_enabled_for_action(action, request):
        return ''

    cfg = get_turnstile_settings()
    if not cfg['enabled'] or not cfg['site_key']:
        return ''

    return format_html(
        '<script src="{}" async defer></script>',
        'https://challenges.cloudflare.com/turnstile/v0/api.js',
    )


@register.simple_tag(takes_context=True)
def is_turnstile_active(context, action):
    """Check whether Turnstile is active for a given action."""
    request = context.get('request')
    return is_turnstile_enabled_for_action(action, request)
