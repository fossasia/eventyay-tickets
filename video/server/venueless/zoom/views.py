import datetime
from calendar import timegm

import jwt
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views.generic import TemplateView

from venueless.core.models import World


def generate_signature(data):
    iat = datetime.datetime.utcnow()
    payload = {
        "appKey": data["apiKey"],
        "sdkKey": data["apiKey"],
        "mn": data["meetingNumber"],
        "role": data["role"],
        "iat": iat,
        "exp": iat + datetime.timedelta(hours=24),
        "tokenExp": timegm((iat + datetime.timedelta(hours=24)).utctimetuple()),
    }
    return jwt.encode(payload, data["apiSecret"], algorithm="HS256")


def get_closest_zoom_lang(world):
    zoom_langs = [
        "de-DE",
        "es-ES",
        "en-US",
        "fr-FR",
        "jp-JP",
        "pt-PT",
        "ru-RU",
        "zh-CN",
        "zh-TW",
        "ko-KO",
        "it-IT",
        "vi-VN",
    ]
    for lang in zoom_langs:
        if lang.lower() == world.locale.lower():
            return lang
    for lang in zoom_langs:
        if lang.lower().startswith(world.locale[:2]):
            return lang
    return "en-US"


class ZoomViewMixin:
    @cached_property
    def world(self):
        w = get_object_or_404(World, domain=self.request.headers["Host"])
        if not settings.DEBUG and "zoom" not in w.feature_flags:
            raise PermissionDenied("Feature disabled")
        return w

    def dispatch(self, request, *args, **kwargs):
        r = super().dispatch(request, *args, **kwargs)
        if "cross-origin-isolation" in self.world.feature_flags:
            r["Cross-Origin-Resource-Policy"] = "cross-origin"
            r["Cross-Origin-Embedder-Policy"] = "require-corp"
            r["Cross-Origin-Opener-Policy"] = "same-origin"
        return r


class MeetingView(ZoomViewMixin, TemplateView):
    template_name = "zoom/meeting.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        try:
            inp = signing.loads(self.request.GET.get("data"), max_age=3600 * 12)
        except signing.BadSignature:
            raise PermissionDenied()

        data = {
            "apiKey": settings.ZOOM_KEY,
            "apiSecret": settings.ZOOM_SECRET,
            "meetingNumber": inp["mn"],
            "role": int(inp["ho"]),
        }

        ctx.update(
            {
                "meeting_number": inp["mn"],
                "api_key": settings.ZOOM_KEY,
                "signature": generate_signature(data),
                "password": inp["pw"],
                "user_name": inp["un"],
                "user_email": "{}@zoom.fake.{}".format(
                    inp["ui"],
                    "debug.venueless.events" if settings.DEBUG else self.world.domain,
                ),
                "support_chat": not inp["dc"],
                "debug": settings.DEBUG,
                "lang": get_closest_zoom_lang(self.world),
                "langurl": "/zoom-de-DE.json"
                if self.world.locale.startswith("de")
                else "",
            }
        )

        return ctx


class MeetingEndedView(ZoomViewMixin, TemplateView):
    template_name = "zoom/ended.html"


class IframeTestView(ZoomViewMixin, TemplateView):
    template_name = "zoom/iframetest.html"
