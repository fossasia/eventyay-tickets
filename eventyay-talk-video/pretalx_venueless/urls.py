from django.urls import path

from . import views

urlpatterns = [
    path(
        "orga/event/<slug:event>/settings/p/eventyay-video/",
        views.Settings.as_view(),
        name="settings",
    ),
    path(
        "<slug:event>/p/eventyay-video/check",
        views.check,
        name="check",
    ),
    path(
        "<slug:event>/p/eventyay-video/join",
        views.SpeakerJoin.as_view(),
        name="join",
    ),
]
