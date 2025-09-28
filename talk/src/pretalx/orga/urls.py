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
    path("reset/", auth.ResetView.as_view(), name="auth.reset"),
    path("reset/<token>", auth.RecoverView.as_view(), name="auth.recover"),
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
    path(
        "organiser/",
        dashboard.DashboardOrganiserListView.as_view(),
        name="organiser.list",
    ),
    path("organiser/new", organiser.OrganiserDetail.as_view(), name="organiser.create"),
    path(
        "organiser/<slug:organiser>/",
        include(
            [
                path(
                    "",
                    dashboard.DashboardOrganiserEventListView.as_view(),
                    name="organiser.dashboard",
                ),
                path(
                    "settings/",
                    organiser.OrganiserDetail.as_view(),
                    name="organiser.settings",
                ),
                path(
                    "settings/delete/",
                    organiser.OrganiserDelete.as_view(),
                    name="organiser.delete",
                ),
                path("api/users", organiser.speaker_search, name="organiser.user_list"),
                *organiser.TeamView.get_urls(
                    url_base="teams",
                    url_name="organiser.teams",
                    namespace="orga",
                ),
                path(
                    "teams/<int:team_pk>/members/<int:user_pk>/delete/",
                    organiser.TeamMemberDelete.as_view(),
                    name="organiser.teams.members.delete",
                ),
                path(
                    "teams/<int:team_pk>/members/<int:user_pk>/reset/",
                    organiser.TeamResetPassword.as_view(),
                    name="organiser.teams.members.reset",
                ),
                path(
                    "teams/<int:pk>/invites/<int:invite_pk>/uninvite/",
                    organiser.TeamUninvite.as_view(),
                    name="organiser.teams.invites.uninvite",
                ),
                path(
                    "teams/<int:pk>/invites/<int:invite_pk>/resend/",
                    organiser.TeamResend.as_view(),
                    name="organiser.teams.invites.resend",
                ),
                path(
                    "speakers/",
                    organiser.OrganiserSpeakerList.as_view(),
                    name="organiser.speakers",
                ),
            ]
        ),
    ),
    
    path("event/new/", event.EventWizard.as_view(), name="event.create"),
    path("event/", dashboard.DashboardEventListView.as_view(), name="event.list"),
    path(
        "event/<slug:event>/",
        include(
            [
                path("login/", auth.LoginView.as_view(), name="event.login"),
                path("reset/", auth.ResetView.as_view(), name="event.auth.reset"),
                path(
                    "reset/<token>",
                    auth.RecoverView.as_view(),
                    name="event.auth.recover",
                ),
                path("delete", event.EventDelete.as_view(), name="event.delete"),
                path("history/", event.EventHistory.as_view(), name="event.history"),
            ]
        ),
    ),
]
