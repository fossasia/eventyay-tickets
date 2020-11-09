import json
import os
import re

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import OperationalError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView

from venueless.core.models import World
from venueless.core.models.auth import ShortToken
from venueless.core.utils.redis import aioredis


class SourceCache:
    @cached_property
    def source(self):
        wapath = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../../webapp/dist/index.html")
        )
        try:
            with open(wapath) as f:
                return f.read()
        except IOError:
            return "<!-- {} not found --><body></body>".format(wapath)


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

    def get(self, request, *args, **kwargs):
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
                            "socket": "wss://{}/ws/world/{}/".format(
                                request.headers["Host"], world.pk
                            ),
                            "upload": reverse("storage:upload"),
                        },
                        "features": world.feature_flags,
                        "locale": world.locale,
                        "dateLocale": world.config.get("dateLocale", "en-ie"),
                        "theme": world.config.get("theme", {}),
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

        return HttpResponse(source, content_type="text/html")


class HealthcheckView(View):
    """
    This view renders the main HTML. It is not used during development but only during production usage.
    """

    @async_to_sync
    async def _check_redis(self):
        async with aioredis() as redis:
            await redis.set("healthcheck", "1")

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
            return redirect("/")
