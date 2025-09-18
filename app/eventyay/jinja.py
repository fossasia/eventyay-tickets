import django.utils.translation
from django.conf import settings
from django.template.defaultfilters import date
from jinja2 import Environment

from .helpers.jinja import url_for


jj_globals = {
    'url_for': url_for,
    'site_url': settings.SITE_URL,
}

jj_filters = {
    'format_date': date,
}


def environment(**options) -> Environment:
    env = Environment(**options)
    # This method is from `jinja2.ext.i18n`
    env.install_gettext_translations(django.utils.translation, newstyle=True)
    env.globals.update(jj_globals)
    env.filters.update(jj_filters)
    return env
