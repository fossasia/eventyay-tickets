import importlib
from contextlib import suppress

from django.apps import apps
from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.urls import re_path

from pretalx.common.views import error_view

plugin_patterns = []
for app in apps.get_app_configs():
    if getattr(app, "PretalxPluginMeta", None):
        if importlib.util.find_spec(app.name + ".urls"):
            urlmod = importlib.import_module(app.name + ".urls")
            single_plugin_patterns = []
            urlpatterns = getattr(urlmod, "urlpatterns", None)
            if urlpatterns:
                single_plugin_patterns += urlpatterns
            plugin_patterns.append(
                re_path(r"", include((single_plugin_patterns, app.label)))
            )

urlpatterns = [
    re_path(r"^400$", error_view(400)),
    re_path(r"^403$", error_view(403)),
    re_path(r"^403/csrf$", error_view(4031)),
    re_path(r"^404$", error_view(404)),
    re_path(r"^500$", error_view(500)),
    re_path(r"^orga/", include("pretalx.orga.urls", namespace="orga")),
    re_path(r"^api/", include("pretalx.api.urls", namespace="api")),
    re_path(r"", include("pretalx.agenda.urls", namespace="agenda")),
    re_path(r"", include("pretalx.cfp.urls", namespace="cfp")),
    re_path(r"", include((plugin_patterns, "plugins"))),
]

handler500 = "pretalx.common.views.handle_500"

if settings.DEBUG:
    with suppress(ImportError):
        import debug_toolbar

        urlpatterns += [
            re_path(r"^__debug__/", include(debug_toolbar.urls)),
        ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
