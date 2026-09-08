from urllib.parse import urljoin

from django.apps import apps
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html
from jinja2 import pass_context
from jinja2.runtime import Context
from markupsafe import Markup

from eventyay.base.services.turnstile import (
    get_turnstile_settings,
    is_turnstile_enabled_for_action,
)


@pass_context
def url_for(context: Context, name: str, *args, query_string=None, **kwargs):
    try:
        current_app = context['request'].current_app
    except KeyError:
        current_app = None
    except AttributeError:
        try:
            current_app = context['request'].resolver_match.namespace
        except AttributeError:
            current_app = None
    base_url = reverse(name, args=args, kwargs=kwargs, current_app=current_app)
    return f'{base_url}?{query_string}' if query_string else base_url


def static_url(path: str = '') -> str:
    """Generate a URL for a static file.

    Mimics Django's {% static %} template tag behavior by resolving static file URLs
    through the configured staticfiles storage backend when available, or falling back
    to simple URL joining with STATIC_URL.

    Args:
        path: Relative path to the static file (e.g., 'css/style.css').
              Defaults to empty string.

    Returns:
        The fully resolved URL to the static file. When django.contrib.staticfiles
        is installed, this includes version hashes and respects custom storage backends.
        Otherwise, returns a simple concatenation of STATIC_URL and the path.

    Example:
        >>> static_url('css/main.css')
        '/static/css/main.css'  # or '/static/css/main.abc123.css' with ManifestStaticFilesStorage

    Reference:
        https://github.com/django/django/blob/main/django/templatetags/static.py#L125
    """
    if apps.is_installed('django.contrib.staticfiles'):
        from django.contrib.staticfiles.storage import staticfiles_storage

        return staticfiles_storage.url(path)
    return urljoin(settings.STATIC_URL, path)


@pass_context
def turnstile_widget(context: Context, action: str = 'registration', theme: str = 'auto', size: str = 'normal'):
    request = context.get('request')
    if not is_turnstile_enabled_for_action(action, request):
        return Markup('')

    cfg = get_turnstile_settings()
    site_key = cfg.get('site_key', '')
    if not site_key:
        return Markup('')

    return Markup(
        format_html(
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
    )


@pass_context
def turnstile_script(context: Context, action: str | None = None):
    request = context.get('request')
    if action and not is_turnstile_enabled_for_action(action, request):
        return Markup('')

    cfg = get_turnstile_settings()
    if not cfg['enabled'] or not cfg['site_key']:
        return Markup('')

    return Markup(
        format_html(
            '<script src="{}" async defer></script>',
            'https://challenges.cloudflare.com/turnstile/v0/api.js',
        )
    )


