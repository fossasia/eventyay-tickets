from django.conf.urls import url

from .views import auth, event, locale, user, wizard

cfp_urls = [
    url('^(?P<event>\w+)/$', event.EventStartpage.as_view(), name='event.start'),
    url('^(?P<event>\w+)/logout$', auth.LogoutView.as_view(), name='event.logout'),
    url('^(?P<event>\w+)/reset$', auth.ResetView.as_view(), name='event.reset'),
    url('^(?P<event>\w+)/reset/(?P<token>\w+)$', auth.RecoverView.as_view(), name='event.recover'),
    url('^(?P<event>\w+)/login', auth.LoginView.as_view(), name='event.login'),

    url('^(?P<event>\w+)/submit/$',
        wizard.SubmitStartView.as_view(),
        name='event.submit'),
    url('^(?P<event>\w+)/submit/(?P<tmpid>.+)/(?P<step>.+)/$',
        wizard.SubmitWizard.as_view(url_name='cfp:event.submit', done_step_name='finished'),
        name='event.submit'),

    url('^(?P<event>\w+)/me$', user.ProfileView.as_view(), name='event.user.view'),
    url('^(?P<event>\w+)/me/submissions$', user.SubmissionsListView.as_view(), name='event.user.submissions'),
    url('^(?P<event>\w+)/me/submissions/(?P<code>\w+)/$', user.SubmissionsEditView.as_view(),
        name='event.user.submission.edit'),
    url('^(?P<event>\w+)/me/submissions/(?P<code>\w+)/withdraw$', user.SubmissionsWithdrawView.as_view(),
        name='event.user.submission.withdraw'),
    url('^(?P<event>\w+)/me/submissions/(?P<code>\w+)/confirm$', user.SubmissionConfirmView.as_view(),
        name='event.user.submission.confirm'),

    url('^locale/set', locale.LocaleSet.as_view(),
        name='locale.set'),

    url('^$', event.GeneralView.as_view()),
]
