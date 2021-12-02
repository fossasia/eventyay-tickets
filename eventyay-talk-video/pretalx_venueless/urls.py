from django.conf.urls import url
from pretalx.event.models.event import SLUG_CHARS

from . import views

urlpatterns = [
    url(
        f"^orga/event/(?P<event>[{SLUG_CHARS}]+)/settings/p/venueless/",
        views.Settings.as_view(),
        name="settings",
    ),
    url(
        f"^(?P<event>[{SLUG_CHARS}]+)/p/venueless/check",
        views.check,
        name="check",
    ),
]
