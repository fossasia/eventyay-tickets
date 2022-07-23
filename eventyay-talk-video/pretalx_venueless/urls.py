from django.urls import path

from . import views

urlpatterns = [
    path(
        "orga/event/<slug:event>/settings/p/venueless/",
        views.Settings.as_view(),
        name="settings",
    ),
    path(
        "<slug:event>/p/venueless/check",
        views.check,
        name="check",
    ),
    path(
        "<slug:event>/p/venueless/join",
        views.SpeakerJoin,
        name="join",
    ),
]
