from django.conf import settings
from django.conf.urls import include, url

from pretalx.event.models.event import SLUG_CHARS

from .views import auth, event, locale, user, wizard

cfp_urls = [
    url(f'^(?P<event>[{SLUG_CHARS}]+)/', include([
        url('^$', event.EventStartpage.as_view(), name='event.start'),
        url('^logout$', auth.LogoutView.as_view(), name='event.logout'),
        url('^reset$', auth.ResetView.as_view(), name='event.reset'),
        url('^reset/(?P<token>\w+)$', auth.RecoverView.as_view(), name='event.recover'),
        url('^login', auth.LoginView.as_view(), name='event.login'),

        url('^submit/$', wizard.SubmitStartView.as_view(), name='event.submit'),
        url('^submit/(?P<tmpid>.+)/(?P<step>.+)/$',
            wizard.SubmitWizard.as_view(url_name='cfp:event.submit', done_step_name='finished'),
            name='event.submit'),

        url('^me$', user.ProfileView.as_view(), name='event.user.view'),
        url('^me/delete$', user.DeleteAccountView.as_view(), name='event.user.delete'),
        url('^me/submissions$', user.SubmissionsListView.as_view(), name='event.user.submissions'),
        url('^me/submissions/(?P<code>\w+)/$', user.SubmissionsEditView.as_view(),
            name='event.user.submission.edit'),
        url('^me/submissions/(?P<code>\w+)/withdraw$', user.SubmissionsWithdrawView.as_view(),
            name='event.user.submission.withdraw'),
        url('^me/submissions/(?P<code>\w+)/confirm$', user.SubmissionConfirmView.as_view(),
            name='event.user.submission.confirm'),

        url('^locale/set', locale.LocaleSet.as_view(), name='locale.set'),
    ])),
]

if settings.DEBUG:
    cfp_urls += [
        url('^$', event.GeneralView.as_view()),
    ]
