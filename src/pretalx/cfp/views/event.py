from contextlib import suppress

import pytz
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation.trans_real import (
    get_supported_language_variant, language_code_re, parse_accept_lang_header,
)
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.event.models import Event


class EventPageMixin(PermissionRequired):
    permission_required = 'cfp.view_event'

    def get_permission_object(self):
        return getattr(self.request, 'event', None)

    def dispatch(self, request, *args, **kwargs):
        self._select_locale(request)
        return super().dispatch(request, *args, **kwargs)

    def _language_from_browser(self, request, supported):
        accept_value = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        for accept_lang, unused in parse_accept_lang_header(accept_value):
            if accept_lang == '*':
                break

            if not language_code_re.search(accept_lang):
                continue

            try:
                val = get_supported_language_variant(accept_lang)
                if val and val in supported:
                    return val
            except LookupError:
                continue

    def _language_from_cookie(self, request, supported):
        cookie_value = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        with suppress(LookupError):
            cookie_value = get_supported_language_variant(cookie_value)
            if cookie_value and cookie_value in supported:
                return cookie_value

    def _language_from_user(self, request, supported):
        if request.user.is_authenticated:
            with suppress(LookupError):
                value = get_supported_language_variant(request.user.locale)
                if value and value in supported:
                    return value

    def _select_locale(self, request):
        supported = request.event.locales
        language = (
            self._language_from_user(request, supported)
            or self._language_from_cookie(request, supported)
            or self._language_from_browser(request, supported)
            or request.event.locale
        )

        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        with suppress(pytz.UnknownTimeZoneError):
            tzname = request.event.timezone
            timezone.activate(pytz.timezone(tzname))
            request.timezone = tzname


class LoggedInEventPageMixin(EventPageMixin, LoginRequiredMixin):

    def get_login_url(self) -> str:
        return reverse('cfp:event.login', kwargs={
            'event': self.request.event.slug
        })


class EventStartpage(EventPageMixin, TemplateView):
    template_name = 'cfp/event/index.html'


class EventCfP(EventPageMixin, TemplateView):
    template_name = 'cfp/event/cfp.html'


class GeneralView(TemplateView):
    template_name = 'cfp/index.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['events'] = Event.objects.filter(is_public=True)
        ctx['orga_events'] = [e for e in Event.objects.filter(is_public=False) if self.request.user.has_perm('cfp.view_event', e)]
        return ctx
