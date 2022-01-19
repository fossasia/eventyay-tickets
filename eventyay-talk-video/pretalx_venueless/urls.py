from pretalx.event.models.event import SLUG_CHARS
from django.urls import path

from . import views

urlpatterns = [
    path(
        f"orga/event/<slug:event>/settings/p/venueless/",
        views.Settings.as_view(),
        name="settings",
    ),
    path(
        f"<slug:event>/p/venueless/check",
        views.check,
        name="check",
    ),
]
