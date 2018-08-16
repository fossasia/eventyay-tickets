from django.conf.urls import include, url
from django.views.generic import RedirectView

from pretalx.event.models.event import SLUG_CHARS

from .views import auth, event, locale, robots, user, wizard

app_name = 'cfp'
urlpatterns = [
    url(
        f'^(?P<event>[{SLUG_CHARS}]+)/',
        include(
            [
                url('^$', event.EventStartpage.as_view(), name='event.landing'),
                url('^logout$', auth.LogoutView.as_view(), name='event.logout'),
                url('^auth/$', auth.EventAuth.as_view(), name='event.auth'),
                url('^reset$', auth.ResetView.as_view(), name='event.reset'),
                url('^login', auth.LoginView.as_view(), name='event.login'),
                url(
                    r'^reset/(?P<token>\w+)$',
                    auth.RecoverView.as_view(),
                    name='event.recover',
                ),
                url('^cfp$', event.EventCfP.as_view(), name='event.start'),
                url('^submit/$', wizard.SubmitStartView.as_view(), name='event.submit'),
                url(
                    '^submit/(?P<tmpid>.+)/(?P<step>.+)/$',
                    wizard.SubmitWizard.as_view(
                        url_name='cfp:event.submit', done_step_name='finished'
                    ),
                    name='event.submit',
                ),
                url(
                    r'^invitation/(?P<code>\w+)/(?P<invitation>\w+)$',
                    user.SubmissionInviteAcceptView.as_view(),
                    name='invitation.view',
                ),
                url('^me$', user.ProfileView.as_view(), name='event.user.view'),
                url(
                    '^me/delete$',
                    user.DeleteAccountView.as_view(),
                    name='event.user.delete',
                ),
                url(
                    '^me/submissions$',
                    user.SubmissionsListView.as_view(),
                    name='event.user.submissions',
                ),
                url(
                    r'^me/submissions/(?P<code>[\w-]+)/',
                    include(
                        [
                            url(
                                '^$',
                                user.SubmissionsEditView.as_view(),
                                name='event.user.submission.edit',
                            ),
                            url(
                                '^withdraw$',
                                user.SubmissionsWithdrawView.as_view(),
                                name='event.user.submission.withdraw',
                            ),
                            url(
                                '^confirm$',
                                user.SubmissionConfirmView.as_view(),
                                name='event.user.submission.confirm',
                            ),
                            url(
                                '^invite$',
                                user.SubmissionInviteView.as_view(),
                                name='event.user.submission.invite',
                            ),
                        ]
                    ),
                ),
                url('^locale/set', locale.LocaleSet.as_view(), name='locale.set'),
            ]
        ),
    ),
    url(
        r'^control/(?P<path>.*)$',
        RedirectView.as_view(url='/orga/%(path)s'),
        name='notpretix',
    ),
    url(r'^robots.txt$', robots.robots_txt, name='robots.txt'),
    url('^$', event.GeneralView.as_view()),
]
