import json
import os
import re

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import OperationalError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from venueless.core.models import Feedback, World
from venueless.core.models.auth import ShortToken


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

        source = re.sub("<html[^>]*>", '<html lang="{}">'.format(world.locale), source)

        return HttpResponse(source, content_type="text/html")


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
            return redirect("/")


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
