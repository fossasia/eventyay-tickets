from django.conf.urls import include
from django.urls import re_path
from django.views.generic import RedirectView

from pretalx.event.models.event import SLUG_CHARS

from .views import auth, event, locale, robots, user, wizard

app_name = "cfp"
urlpatterns = [
    re_path(
        f"^(?P<event>[{SLUG_CHARS}]+)/",
        include(
            [
                re_path("^$", event.EventStartpage.as_view(), name="event.landing"),
                re_path("^logout$", auth.LogoutView.as_view(), name="event.logout"),
                re_path("^auth/$", auth.EventAuth.as_view(), name="event.auth"),
                re_path("^reset$", auth.ResetView.as_view(), name="event.reset"),
                re_path("^login/$", auth.LoginView.as_view(), name="event.login"),
                re_path(
                    r"^reset/(?P<token>\w+)$",
                    auth.RecoverView.as_view(),
                    name="event.recover",
                ),
                re_path("^cfp$", event.EventCfP.as_view(), name="event.start"),
                re_path(
                    "^submit/$", wizard.SubmitStartView.as_view(), name="event.submit"
                ),
                re_path(
                    "^submit/(?P<tmpid>.+)/(?P<step>.+)/$",
                    wizard.SubmitWizard.as_view(),
                    name="event.submit",
                ),
                re_path(
                    r"^invitation/(?P<code>\w+)/(?P<invitation>\w+)$",
                    user.SubmissionInviteAcceptView.as_view(),
                    name="invitation.view",
                ),
                re_path("^me/$", user.ProfileView.as_view(), name="event.user.view"),
                re_path(
                    "^me/delete$",
                    user.DeleteAccountView.as_view(),
                    name="event.user.delete",
                ),
                re_path(
                    "^me/submissions/$",
                    user.SubmissionsListView.as_view(),
                    name="event.user.submissions",
                ),
                re_path(
                    "^me/mails/$", user.MailListView.as_view(), name="event.user.mails",
                ),
                re_path(
                    r"^me/submissions/(?P<code>[\w-]+)/",
                    include(
                        [
                            re_path(
                                r"^$",
                                user.SubmissionsEditView.as_view(),
                                name="event.user.submission.edit",
                            ),
                            re_path(
                                r"^withdraw$",
                                user.SubmissionsWithdrawView.as_view(),
                                name="event.user.submission.withdraw",
                            ),
                            re_path(
                                r"^confirm$",
                                user.SubmissionConfirmView.as_view(),
                                name="event.user.submission.confirm",
                            ),
                            re_path(
                                r"^invite$",
                                user.SubmissionInviteView.as_view(),
                                name="event.user.submission.invite",
                            ),
                        ]
                    ),
                ),
                re_path(r"^locale/set", locale.LocaleSet.as_view(), name="locale.set"),
            ]
        ),
    ),
    re_path(r"^locale/set", locale.LocaleSet.as_view(), name="locale.set_global"),
    re_path(
        r"^control/(?P<path>.*)$",
        RedirectView.as_view(url="/orga/%(path)s"),
        name="notpretix",
    ),
    re_path(r"^robots.txt$", robots.robots_txt, name="robots.txt"),
    re_path(r"^$", event.GeneralView.as_view(), name="root.main"),
]
