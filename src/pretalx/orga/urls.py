from django.conf.urls import url

from .views import auth, cfp, dashboard, settings

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),
    url('^event/new/', settings.EventCreate.as_view(), name='event.create'),

    url('^event/(?P<event>\w+)/cfp/questions/(?P<pk>[0-9]+)/edit/', cfp.CfPQuestionUpdate.as_view(), name='cfp.questions.edit'),
    url('^event/(?P<event>\w+)/cfp/questions/(?P<pk>[0-9]+)/delete/', cfp.CfPQuestionDelete.as_view(), name='cfp.questions.delete'),
    url('^event/(?P<event>\w+)/cfp/questions/', cfp.CfPQuestionsDetail.as_view(), name='cfp.questions.view'),
    url('^event/(?P<event>\w+)/cfp/text/edit/', cfp.CfPTextUpdate.as_view(), name='cfp.text.edit'),
    url('^event/(?P<event>\w+)/cfp/text/', cfp.CfPTextDetail.as_view(), name='cfp.text.view'),

    url('^event/(?P<event>\w+)/settings/edit/', settings.EventUpdate.as_view(), name='settings.event.edit'),
    url('^event/(?P<event>\w+)/settings/', settings.EventDetail.as_view(), name='settings.event.view'),

    url('^event/(?P<event>\w+)/$', dashboard.EventDashboardView.as_view(), name='event.dashboard'),
    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
]
