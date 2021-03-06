import base64
import hashlib
import hmac
import time

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views.generic import TemplateView

from venueless.core.models import World


def generate_signature(data):
    # From https://marketplace.zoom.us/docs/sdk/native-sdks/web/build/signature
    ts = int(round(time.time() * 1000)) - 30000
    msg = data["apiKey"] + str(data["meetingNumber"]) + str(ts) + str(data["role"])
    message = base64.b64encode(bytes(msg, "utf-8"))
    # message = message.decode("utf-8");
    secret = bytes(data["apiSecret"], "utf-8")
    hash = hmac.new(secret, message, hashlib.sha256)
    hash = base64.b64encode(hash.digest())
    hash = hash.decode("utf-8")
    tmpString = "%s.%s.%s.%s.%s" % (
        data["apiKey"],
        str(data["meetingNumber"]),
        str(ts),
        str(data["role"]),
        hash,
    )
    signature = base64.b64encode(bytes(tmpString, "utf-8"))
    signature = signature.decode("utf-8")
    return signature.rstrip("=")


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
                "debug": settings.DEBUG,
                "lang": get_closest_zoom_lang(self.world),
            }
        )

        return ctx


class MeetingEndedView(ZoomViewMixin, TemplateView):
    template_name = "zoom/ended.html"
