import os

from django import template
from django.utils.safestring import mark_safe
from django.templatetags.static import static
from django.contrib.staticfiles.storage import staticfiles_storage

from statici18n.conf import settings
from statici18n.utils import get_filename

register = template.Library()


def get_path(locale):
    return os.path.join(
        settings.STATICI18N_OUTPUT_DIR, get_filename(locale, settings.STATICI18N_DOMAIN)
    )


@register.simple_tag
def statici18n(locale):
    """
    A template tag that returns the URL to a Javascript catalog
    for the selected locale.

    Behind the scenes, this is a thin wrapper around staticfiles's static
    template tag.
    """
    return static(get_path(locale))


@register.simple_tag
def inlinei18n(locale):
    """
    A template tag that returns the Javascript catalog content
    for the selected locale to be inlined in a <script></script> block.

    Behind the scenes, this is a thin wrapper around staticfiles's configred
    storage
    """
    return mark_safe(staticfiles_storage.open(get_path(locale)).read().decode())
