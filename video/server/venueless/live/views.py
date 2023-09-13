import json
import os
import re
from urllib.parse import urljoin, urlparse

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import OperationalError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from venueless.core.models import Feedback, World
from venueless.core.models.auth import ShortToken
from venueless.core.models.room import AnonymousInvite


class SourceCache:
    @cached_property
    def source(self):
        wapath = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../../webapp/dist/index.html")
        )
        try:
            with open(wapath) as f:
                return f.read()
        except OSError:
            return f"<!-- {wapath} not found --><body></body>"


sh = SourceCache()


class ManifestView(View):
    def get(self, request, *args, **kwargs):
        world = get_object_or_404(World, domain=request.headers["Host"])
        # TODO: Allow to parametrize colors and logos
        source = {
            "name": world.title,
            "short_name": world.title,
            "theme_color": "#180044",
            "icons": [
                {
                    "src": "/venueless-logo.192.png",
                    "type": "image/png",
                    "sizes": "192x192",
                },
                {
                    "src": "/venueless-logo.512.png",
                    "type": "image/png",
                    "sizes": "512x512",
                },
                {"src": "/venueless-logo.svg", "sizes": "192x192 512x512"},
            ],
            "start_url": ".",
            "display": "standalone",
            "background_color": "#000000",
        }
        return JsonResponse(source)


class AppView(View):
    """
    This view renders the main HTML. It is not used during development but only during production usage.
    """

    @cached_property
    def _has_separate_short_domain(self):
        shorturl_host = urlparse(settings.SHORT_URL).hostname
        siteurl_host = urlparse(settings.SITE_URL).hostname
        if shorturl_host != siteurl_host:
            return shorturl_host
        return False

    def get(self, request, *args, **kwargs):
        # Is this an anonymous invite to a room?
        short_host = self._has_separate_short_domain
        if short_host and request.headers["Host"] == short_host:
            # The sysadmin has set up a separate domain for short URLs
            if request.path == "/":
                # This must be a 200, not a 302 or 404, so the domain is considered "active"
                # by our auto-SSL setup in the venueless.events production deployment
                return render(request, "live/short_domain_index.html")
            else:
                try:
                    invite = AnonymousInvite.objects.get(
                        expires__gte=now(),
                        short_token=request.path[1:],
                    )
                except AnonymousInvite.DoesNotExist:
                    return render(request, "live/short_domain_invalid.html", status=404)
                return redirect(
                    urljoin(
                        request.scheme + "://" + invite.world.domain,
                        f"/standalone/{invite.room_id}/anonymous#invite={invite.short_token}",
                    )
                )
        elif not short_host and len(request.path) == 7:
            # The sysadmin has not set up a separate domain for short URLs
            try:
                invite = AnonymousInvite.objects.get(
                    expires__gte=now(),
                    short_token=request.path[1:],
                )
                return redirect(
                    urljoin(
                        request.scheme + "://" + invite.world.domain,
                        f"/standalone/{invite.room_id}/anonymous#invite={invite.short_token}",
                    )
                )
            except AnonymousInvite.DoesNotExist:
                # We do not show a 404 since theoretically this could be a vlaid path recognized by
                # the frontend router.
                pass

        try:
            world = get_object_or_404(World, domain=request.headers["Host"])
        except OperationalError:
            # We use connection pooling, so if the database server went away since the last connection
            # terminated, Django won't know and we'll get an OperationalError. We just silently re-try
            # once, since Django will then use a new connection.
            world = get_object_or_404(World, domain=request.headers["Host"])
        source = sh.source
        source = re.sub(
            "<title>[^<]*</title>",
            f"<title>{world.title}</title>",
            source,
            re.IGNORECASE | re.MULTILINE,
        )
        source = source.replace(
            "<body>",
            "<script>window.venueless={}</script><body>".format(
                json.dumps(
                    {
                        "api": {
                            "base": reverse("api:root", kwargs={"world_id": world.id}),
                            "socket": "{}://{}/ws/world/{}/".format(
                                settings.WEBSOCKET_PROTOCOL,
                                request.headers["Host"],
                                world.pk,
                            ),
                            "upload": reverse("storage:upload"),
                            "scheduleImport": reverse("storage:schedule_import"),
                            "feedback": reverse("live:feedback"),
                        },
                        "features": world.feature_flags,
                        "externalAuthUrl": world.external_auth_url,
                        "locale": world.locale,
                        "dateLocale": world.config.get("dateLocale", "en-ie"),
                        "theme": world.config.get("theme", {}),
                        "videoPlayer": world.config.get("videoPlayer", {}),
                        "mux": world.config.get("mux", {}),
                    }
                )
            ),
        )
        if world.config.get("theme", {}).get("css", ""):
            source = source.replace(
                "<body>",
                "<link rel='stylesheet' href='{}'><body>".format(
                    reverse("live:css.custom")
                ),
            )

        source = re.sub("<html[^>]*>", f'<html lang="{world.locale}">', source)

        r = HttpResponse(source, content_type="text/html")
        if "cross-origin-isolation" in world.feature_flags:
            r["Cross-Origin-Resource-Policy"] = "cross-origin"
            r["Cross-Origin-Embedder-Policy"] = "require-corp"
            r["Cross-Origin-Opener-Policy"] = "same-origin"
        return r


class HealthcheckView(View):
    """
    This view renders the main HTML. It is not used during development but only during production usage.
    """

    @async_to_sync
    async def _check_redis(self):
        await get_channel_layer().send("healthcheck_channel", {"type": "healthcheck"})

    def get(self, request, *args, **kwargs):
        self._check_redis()
        World.objects.count()
        return HttpResponse("OK")


@method_decorator(cache_page(1 if settings.DEBUG else 60), name="dispatch")
class CustomCSSView(View):
    def get(self, request, *args, **kwargs):
        world = get_object_or_404(World, domain=request.headers["Host"])
        source = world.config.get("theme", {}).get("css", "")
        return HttpResponse(source, content_type="text/css")


@method_decorator(cache_page(1 if settings.DEBUG else 60), name="dispatch")
class BBBCSSView(TemplateView):
    template_name = "live/bbb.css"
    content_type = "text/css"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx["world"] = get_object_or_404(World, domain=self.request.headers["Host"])
        return ctx


class ShortTokenView(View):
    def get(self, request, token):
        world = get_object_or_404(World, domain=self.request.headers["Host"])
        try:
            st = ShortToken.objects.get(short_token=token, world=world)
            return redirect(f"/#token={st.long_token}")
        except ShortToken.DoesNotExist:
            return HttpResponse(
                "Unknown access token. Please check that you clicked the correct link."
            )


class FeedbackView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def world(self):
        return get_object_or_404(World, domain=self.request.headers["Host"])

    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        Feedback.objects.create(
            world=self.world,
            module=data.get("module"),
            message=data.get("message"),
            trace=data.get("trace"),
        )
        return JsonResponse({}, status=201)
