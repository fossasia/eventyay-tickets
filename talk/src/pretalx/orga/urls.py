from django.urls import include, path
from django.views.generic.base import RedirectView

from pretalx.eventyay_common.views import sso
from pretalx.orga.views import (
    admin,
    auth,
    cards,
    cfp,
    dashboard,
    event,
    mails,
    organiser,
    person,
    plugins,
    review,
    schedule,
    speaker,
    submission,
    typeahead,
)

app_name = "orga"
urlpatterns = [
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("", RedirectView.as_view(url="event", permanent=False), name="base"),
    path(
        "admin/sso/",
        include(
            [
                path(
                    "settings",
                    sso.SSOConfigureView.as_view(),
                    name="admin.sso.settings",
                ),
                path("delete", sso.SSODeleteView.as_view(), name="admin.sso.delete"),
            ]
        ),
    ),
    path("start/redirect", dashboard.start_redirect_view, name="start.redirect"),
    
]
