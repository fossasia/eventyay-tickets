from django.conf.urls import url

from .views import auth, event, user, wizard

cfp_urls = [
    url('^(?P<event>\w+)/$', event.EventStartpage.as_view(), name='event.start'),
    url('^(?P<event>\w+)/logout$', auth.LogoutView.as_view(), name='event.logout'),
    url('^(?P<event>\w+)/login', event.EventStartpage.as_view(), name='event.login'),  # TODO: implement
    url('^(?P<event>\w+)/submit/$',
        wizard.SubmitStartView.as_view(),
        name='event.submit'),
    url('^(?P<event>\w+)/submit/(?P<tmpid>.+)/(?P<step>.+)/$',
        wizard.SubmitWizard.as_view(url_name='cfp:event.submit', done_step_name='finished'),
        name='event.submit'),
    url('^(?P<event>\w+)/thanks$', event.EventStartpage.as_view(), name='event.thanks'),
    url('^(?P<event>\w+)/me/submissions$', user.SubmissionsListView.as_view(), name='event.user.submissions'),
]
