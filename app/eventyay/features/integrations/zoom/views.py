import datetime
import re
from urllib.parse import quote

import jwt
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.functional import cached_property
from django.views.generic import TemplateView

from eventyay.base.models import Event


def generate_signature(data_or_key, api_secret=None, meeting_number=None, role=0):
    if isinstance(data_or_key, dict):
        api_key = data_or_key.get("apiKey") or data_or_key.get("client_id") or ""
        api_secret = data_or_key.get("apiSecret") or data_or_key.get("client_secret") or ""
        meeting_number = data_or_key.get("meetingNumber") or data_or_key.get("mn") or ""
        role = data_or_key.get("role", 0)
    else:
        api_key = data_or_key or ""

    if not api_key or not api_secret:
        return ""

    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    exp = now + 86400
    payload = {
        "appKey": str(api_key),
        "sdkKey": str(api_key),
        "mn": str(meeting_number),
        "role": int(role),
        "iat": now,
        "exp": exp,
        "tokenExp": exp,
    }
    try:
        return jwt.encode(payload, str(api_secret), algorithm="HS256")
    except Exception:
        return ""


def get_closest_zoom_lang(event):
    if not event or not getattr(event, "locale", None):
        return "en-US"
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
        if lang.lower() == event.locale.lower():
            return lang
    for lang in zoom_langs:
        if lang.lower().startswith(event.locale[:2]):
            return lang
    return "en-US"


from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt


@method_decorator(xframe_options_exempt, name="dispatch")
class ZoomViewMixin:
    @cached_property
    def event(self):
        # 1. Inspect signed data payload if present
        raw_data = self.request.GET.get("data")
        if raw_data:
            try:
                payload = signing.loads(raw_data, max_age=3600 * 12)
                event_id = payload.get("event_id")
                if event_id:
                    ev = Event.objects.filter(id=event_id).first()
                    if ev:
                        return ev
            except Exception:
                pass

        # 2. Match host domain
        event_domain = re.sub(r":\d+$", "", self.request.get_host())
        ev = Event.objects.filter(domain=event_domain).first()
        if ev:
            return ev

        # 3. Development fallback
        if settings.DEBUG:
            ev = Event.objects.first()
            if ev:
                return ev

        raise Http404("Event not found")

    def dispatch(self, request, *args, **kwargs):
        r = super().dispatch(request, *args, **kwargs)
        r.xframe_options_exempt = True
        if "X-Frame-Options" in r:
            del r["X-Frame-Options"]
        r._csp_ignore = True
        if self.event and "cross-origin-isolation" in (self.event.feature_flags or {}):
            r["Cross-Origin-Resource-Policy"] = "cross-origin"
            r["Cross-Origin-Embedder-Policy"] = "require-corp"
            r["Cross-Origin-Opener-Policy"] = "same-origin"
        return r


@method_decorator(xframe_options_exempt, name="dispatch")
class MeetingView(ZoomViewMixin, TemplateView):
    template_name = "zoom/meeting.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        raw_data = self.request.GET.get("data")
        if not raw_data:
            raise PermissionDenied("Missing meeting data")

        try:
            inp = signing.loads(raw_data, max_age=3600 * 12)
        except signing.BadSignature:
            raise PermissionDenied("Invalid meeting data")

        meeting_num = str(inp.get("mn", "")).strip()
        passcode = str(inp.get("pw", "")).strip()
        user_name = str(inp.get("un", "Attendee")).strip()
        role = int(bool(inp.get("ho", False)))

        client_id = (
            inp.get("client_id")
            or getattr(settings, "ZOOM_KEY", "")
            or ""
        )
        client_secret = (
            inp.get("client_secret")
            or getattr(settings, "ZOOM_SECRET", "")
            or ""
        )

        signature = generate_signature(client_id, client_secret, meeting_num, role)
        has_sdk_credentials = bool(client_id and client_secret and signature)

        encoded_user = quote(user_name)
        zoom_app_url = f"zoommtg://zoom.us/join?confno={meeting_num}&pwd={passcode}&uname={encoded_user}"
        zoom_web_url = f"https://zoom.us/wc/{meeting_num}/join?pwd={passcode}&uname={encoded_user}"
        zoom_join_url = f"https://zoom.us/j/{meeting_num}?pwd={passcode}" if passcode else f"https://zoom.us/j/{meeting_num}"

        user_domain = (
            self.event.domain
            if (self.event and self.event.domain)
            else ("debug.eventyay.events" if settings.DEBUG else "eventyay.events")
        )
        user_email = f"{inp.get('ui', 'user')}@zoom.{user_domain}"

        langurl = (
            "/zoom-de-DE.json"
            if self.event and getattr(self.event, "locale", "").startswith("de")
            else ""
        )
        ctx.update(
            {
                "meeting_number": meeting_num,
                "password": passcode,
                "user_name": user_name,
                "user_email": user_email,
                "api_key": client_id,
                "signature": signature,
                "has_sdk_credentials": has_sdk_credentials,
                "zoom_app_url": zoom_app_url,
                "zoom_web_url": zoom_web_url,
                "zoom_join_url": zoom_join_url,
                "support_chat": not inp.get("dc", False),
                "debug": settings.DEBUG,
                "lang": get_closest_zoom_lang(self.event),
                "langurl": langurl,
                "zoom_config": {
                    "hasSdkCredentials": has_sdk_credentials,
                    "meetingNumber": meeting_num,
                    "userName": user_name,
                    "userEmail": user_email,
                    "password": passcode,
                    "signature": signature,
                    "apiKey": client_id,
                    "zoomWebUrl": zoom_web_url,
                    "zoomAppUrl": zoom_app_url,
                    "supportChat": not inp.get("dc", False),
                    "debug": bool(settings.DEBUG),
                    "lang": get_closest_zoom_lang(self.event),
                    "langUrl": langurl,
                    "leaveUrl": "/zoom/ended/",
                },
            }
        )

        return ctx


class MeetingEndedView(ZoomViewMixin, TemplateView):
    template_name = "zoom/ended.html"

    @cached_property
    def event(self):
        try:
            return super().event
        except Http404:
            return None


class IframeTestView(ZoomViewMixin, TemplateView):
    template_name = "zoom/iframetest.html"
