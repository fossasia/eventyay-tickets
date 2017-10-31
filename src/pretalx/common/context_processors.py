from contextlib import suppress

from django.conf import settings
from django.http import Http404
from django.urls import resolve

from pretalx.event.models import Event
from pretalx.orga.utils.i18n import get_javascript_format, get_moment_locale


def add_events(request):
    if request.resolver_match and request.resolver_match.namespace == 'orga' and not request.user.is_anonymous:
        try:
            url_name = resolve(request.path_info).url_name
        except Http404:
            url_name = ''
        return {
            'events': list(Event.objects.filter(permissions__is_orga=True, permissions__user=request.user).distinct()),
            'url_name': url_name,
        }
    return dict()


def locale_context(request):
    ctx = {}
    ctx['js_datetime_format'] = get_javascript_format('DATETIME_INPUT_FORMATS')
    ctx['js_date_format'] = get_javascript_format('DATE_INPUT_FORMATS')
    ctx['js_locale'] = get_moment_locale()
    return ctx


def messages(request):
    from pretalx.common.phrases import phrases
    return {'phrases': phrases}


def system_information(request):
    ctx = {}
    if settings.DEBUG:
        ctx['development_warning'] = True
        with suppress(Exception):
            import subprocess
            ctx['pretalx_version'] = subprocess.check_output(['git', 'describe', '--always'])
    return ctx
