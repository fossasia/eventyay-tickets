from django.urls import include, re_path

from .api.urls import urlpatterns as api_patterns
from .live import views

urlpatterns = [
    re_path(r"^api/v1/", include(api_patterns)),
    re_path(r"(.*)", views.AppView.as_view()),
]
