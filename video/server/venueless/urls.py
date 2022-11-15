import re
from urllib.parse import urlsplit

from decorator_include import decorator_include
from django.conf import settings
from django.urls import include, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from multifactor.decorators import multifactor_protected

from .api.urls import urlpatterns as api_patterns
from .control import urls as control
from .graphs import urls as graphs
from .live import urls as live
from .live import views
from .social import urls as social
from .storage import urls as storage
from .zoom import urls as zoom


def static(prefix, view=serve, **kwargs):
    if not settings.DEBUG or urlsplit(prefix).hostname != "localhost":
        # No-op if not in debug mode or a non-local prefix.
        return []
    return [
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(urlsplit(prefix).path.lstrip("/")),
            view,
            kwargs=kwargs,
        ),
    ]


urlpatterns = (
    [
        re_path(r"^api/v1/", include((api_patterns, "api"), namespace="api")),
        re_path(r"^healthcheck/", views.HealthcheckView.as_view()),
        re_path(r"^manifest.json", views.ManifestView.as_view()),
        re_path(r"graphs/", include(graphs)),
        re_path(r"zoom/", include((zoom, "zoom"), namespace="zoom")),
        re_path(r"storage/", include((storage, "storage"), namespace="storage")),
        re_path(r"social/", include((social, "social"), namespace="social")),
        re_path("control$", RedirectView.as_view(url="/control/")),
        re_path("control/multifactor/", include("multifactor.urls")),
        re_path(
            "control/",
            decorator_include(
                multifactor_protected(
                    factors=1 if settings.VENUELESS_MULTIFACTOR_REQUIRE else 0
                ),
                (control, "control"),
                namespace="control",
            ),
        ),
        re_path(r"", include((live, "live"), namespace="live")),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + [
        re_path(r"(.*)", views.AppView.as_view()),
    ]
)
