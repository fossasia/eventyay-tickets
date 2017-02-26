from django.conf.urls import url

from .views import event, wizard

cfp_urls = [
    url('^(?P<event>\w+)/$', event.EventStartpage.as_view(), name='event.start'),
    url('^(?P<event>\w+)/submit/$',
        wizard.SubmitStartView.as_view(),
        name='event.submit'),
    url('^(?P<event>\w+)/submit/(?P<tmpid>.+)/(?P<step>.+)/$',
        wizard.SubmitWizard.as_view(url_name='cfp:event.submit', done_step_name='finished'),
        name='event.submit'),
]
