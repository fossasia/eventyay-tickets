from contextlib import suppress

from django.conf import settings
from django.http import Http404
from django.urls import resolve

from pretalx.cfp.signals import footer_link
from pretalx.orga.utils.i18n import get_javascript_format, get_moment_locale


def add_events(request):
    if (
        request.resolver_match
        and set(request.resolver_match.namespaces) & {'orga', 'plugins'}
        and not request.user.is_anonymous
    ):
        try:
            url = resolve(request.path_info)
            url_name = url.url_name
            url_namespace = url.namespace
        except Http404:
            url_name = ''
            url_namespace = ''
        return {'url_name': url_name, 'url_namespace': url_namespace}
    return dict()


def locale_context(request):
    context = {}
    context['js_datetime_format'] = get_javascript_format('DATETIME_INPUT_FORMATS')
    context['js_date_format'] = get_javascript_format('DATE_INPUT_FORMATS')
    context['js_locale'] = get_moment_locale()
    return context


def messages(request):
    from pretalx.common.phrases import phrases

    return {'phrases': phrases}


def system_information(request):
    context = {}
    _footer = []
    for _, response in footer_link.send(
        getattr(request, 'event', None), request=request
    ):
        if isinstance(response, list):
            _footer += response
        else:
            _footer.append(response)
    context['footer_links'] = _footer

    if settings.DEBUG:
        context['development_warning'] = True
        with suppress(Exception):
            import subprocess

            context['pretalx_version'] = (
                subprocess.check_output(['git', 'describe', '--always'])
                .decode()
                .strip()
            )
    else:
        with suppress(Exception):
            import pretalx

            context['pretalx_version'] = pretalx.__version__
    return context
