import sys
import warnings

from django.conf import settings
from django.http import Http404
from django.urls import resolve
from django.utils.translation import gettext_lazy as _

from pretalx.cfp.signals import footer_link, html_head
from pretalx.common.models.settings import GlobalSettings
from pretalx.orga.utils.i18n import get_javascript_format, get_moment_locale


def add_events(request):
    if (
        request.resolver_match
        and set(request.resolver_match.namespaces) & {"orga", "plugins"}
        and not request.user.is_anonymous
    ):
        try:
            url = resolve(request.path_info)
            url_name = url.url_name
            url_namespace = url.namespace
        except Http404:
            url_name = ""
            url_namespace = ""
        return {"url_name": url_name, "url_namespace": url_namespace}
    return {}


def locale_context(request):
    context = {}
    context["js_datetime_format"] = get_javascript_format("DATETIME_INPUT_FORMATS")
    context["js_date_format"] = get_javascript_format("DATE_INPUT_FORMATS")
    context["js_locale"] = get_moment_locale()
    context["quotation_open"] = _("“")
    context["quotation_close"] = _("”")
    return context


def messages(request):
    from pretalx.common.phrases import phrases

    return {"phrases": phrases}


def system_information(request):
    context = {}
    _footer = []
    _head = []
    event = getattr(request, "event", None)

    for __, response in footer_link.send(event, request=request):
        if isinstance(response, list):
            _footer += response
        else:
            _footer.append(response)
            warnings.warn(
                "Please return a list in your footer_link signal receiver, not a dictionary.",
                DeprecationWarning,
            )
    context["footer_links"] = _footer

    if event:
        for receiver, response in html_head.send(event, request=request):
            _head.append(response)
        context["html_head"] = "".join(_head)

    if settings.DEBUG:
        context["development_warning"] = True
        context["pretalx_version"] = settings.PRETALX_VERSION

    context["warning_update_available"] = False
    context["warning_update_check_active"] = False
    gs = GlobalSettings()
    if not request.user.is_anonymous and request.user.is_administrator:
        if gs.settings.update_check_result_warning:
            context["warning_update_available"] = True
        if not gs.settings.update_check_ack and "runserver" not in sys.argv:
            context["warning_update_check_active"] = True
    return context
