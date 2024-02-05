from contextlib import suppress

from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.utils.module_loading import import_string

from pretalx.common.views import error_view

plugin_patterns = []
for app in apps.get_app_configs():
    if getattr(app, "PretalxPluginMeta", None):
        with suppress(ImportError):
            urlpatterns = import_string(f"{app.name}.urls.urlpatterns")
            if urlpatterns:
                plugin_patterns.append(path("", include((urlpatterns, app.label))))

urlpatterns = [
    path("400", error_view(400)),
    path("403", error_view(403)),
    path("403/csrf", error_view(4031)),
    path("404", error_view(404)),
    path("500", error_view(500)),
    path("orga/", include("pretalx.orga.urls", namespace="orga")),
    path("api/", include("pretalx.api.urls", namespace="api")),
    # Root patterns are ordered by precedence:
    # Plugins last, so that they cannot break anything
    path("", include("pretalx.agenda.urls", namespace="agenda")),
    path("", include("pretalx.cfp.urls", namespace="cfp")),
    path("", include((plugin_patterns, "plugins"))),
]

handler500 = "pretalx.common.views.handle_500"

if settings.DEBUG:
    with suppress(ImportError):
        import debug_toolbar

        urlpatterns += [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
