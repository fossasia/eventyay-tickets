from django.urls import include, re_path

from .api.urls import urlpatterns as api_patterns
from .graphs import urls as graphs
from .live import views

urlpatterns = [
    re_path(r"^api/v1/", include(api_patterns)),
    re_path(r"^healthcheck/", views.HealthcheckView.as_view()),
    re_path(r"^manifest.json", views.ManifestView.as_view()),
    re_path(r"graphs/", include(graphs)),
    re_path(r"(.*)", views.AppView.as_view()),
]
