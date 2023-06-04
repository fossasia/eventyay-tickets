import datetime as dt
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import override
from django.views.generic import View

from pretalx.common.phrases import phrases


class LocaleSet(View):
    def get(self, request, *args, **kwargs):
        url = request.GET.get("next", request.headers.get("Referer", "/"))
        if url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            parsed = urlparse(url)
            url = parsed.path
            if parsed.query:
                query = parse_qs(parsed.query)
                query.pop("lang", None)
                query = urlencode(query, doseq=True)
                if query:
                    url = f"{url}?{query}"
        else:
            url = "/"

        resp = HttpResponseRedirect(url)
        locale = request.GET.get("locale")
        if locale in [lc for lc, ll in settings.LANGUAGES]:
            if request.user.is_authenticated:
                request.user.locale = locale
                request.user.save()

            max_age = dt.timedelta(seconds=10 * 365 * 24 * 60 * 60)
            resp.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                locale,
                max_age=max_age,
                expires=(dt.datetime.utcnow() + max_age).strftime(
                    "%a, %d-%b-%Y %H:%M:%S GMT"
                ),
                domain=settings.SESSION_COOKIE_DOMAIN,
            )
            with override(locale):
                messages.success(request, str(phrases.cfp.locale_change_success))

        return resp
