from django.conf.urls import url

from .views import auth, event, user, wizard

cfp_urls = [
    url('^(?P<event>\w+)/$', event.EventStartpage.as_view(), name='event.start'),
    url('^(?P<event>\w+)/logout$', auth.LogoutView.as_view(), name='event.logout'),
    url('^(?P<event>\w+)/login', auth.LoginView.as_view(), name='event.login'),

    url('^(?P<event>\w+)/submit/$',
        wizard.SubmitStartView.as_view(),
        name='event.submit'),
    url('^(?P<event>\w+)/submit/(?P<tmpid>.+)/(?P<step>.+)/$',
        wizard.SubmitWizard.as_view(url_name='cfp:event.submit', done_step_name='finished'),
        name='event.submit'),
    url('^(?P<event>\w+)/thanks$', event.EventStartpage.as_view(), name='event.thanks'),

    url('^(?P<event>\w+)/me$', user.ProfileView.as_view(), name='event.user.view'),
    url('^(?P<event>\w+)/me/change-profile$', user.ProfileChange.as_view(), name='event.user.profile'),
    url('^(?P<event>\w+)/me/change-login$', user.LoginChange.as_view(), name='event.user.login'),
    url('^(?P<event>\w+)/me/submissions$', user.SubmissionsListView.as_view(), name='event.user.submissions'),
    url('^(?P<event>\w+)/me/submissions/(?P<id>\d+)/$', user.SubmissionsEditView.as_view(),
        name='event.user.submission.edit'),
    url('^(?P<event>\w+)/me/submissions/(?P<id>\d+)/withdraw$', user.SubmissionsWithdrawView.as_view(),
        name='event.user.submission.withdraw'),
]
