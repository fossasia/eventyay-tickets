from django.conf.urls import url

from .views import auth, cfp, dashboard, settings, speaker, submission

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),
    url('^event/new/', settings.EventCreate.as_view(), name='event.create'),

    url('^event/(?P<event>\w+)/cfp/questions/(?P<pk>[0-9]+)/edit/', cfp.CfPQuestionUpdate.as_view(), name='cfp.question.edit'),
    url('^event/(?P<event>\w+)/cfp/questions/(?P<pk>[0-9]+)/delete/', cfp.CfPQuestionDelete.as_view(), name='cfp.question.delete'),
    url('^event/(?P<event>\w+)/cfp/questions/(?P<pk>[0-9]+)/', cfp.CfPQuestionDetail.as_view(), name='cfp.question.view'),
    url('^event/(?P<event>\w+)/cfp/questions/new/', cfp.CfPQuestionCreate.as_view(), name='cfp.questions.create'),
    url('^event/(?P<event>\w+)/cfp/questions/', cfp.CfPQuestionList.as_view(), name='cfp.questions.view'),
    url('^event/(?P<event>\w+)/cfp/text/edit/', cfp.CfPTextUpdate.as_view(), name='cfp.text.edit'),
    url('^event/(?P<event>\w+)/cfp/text/edit/', cfp.CfPTextUpdate.as_view(), name='cfp.text.edit'),
    url('^event/(?P<event>\w+)/cfp/text/', cfp.CfPTextDetail.as_view(), name='cfp.text.view'),
    url('^event/(?P<event>\w+)/cfp/types/(?P<pk>[0-9]+)/edit/', cfp.SubmissionTypeUpdate.as_view(), name='cfp.type.edit'),
    url('^event/(?P<event>\w+)/cfp/types/(?P<pk>[0-9]+)/delete/', cfp.SubmissionTypeDelete.as_view(), name='cfp.type.delete'),
    url('^event/(?P<event>\w+)/cfp/types/(?P<pk>[0-9]+)/default/', cfp.SubmissionTypeDefault.as_view(), name='cfp.type.default'),
    url('^event/(?P<event>\w+)/cfp/types/new/', cfp.SubmissionTypeCreate.as_view(), name='cfp.types.create'),
    url('^event/(?P<event>\w+)/cfp/types/', cfp.SubmissionTypeList.as_view(), name='cfp.types.view'),

    url('^event/(?P<event>\w+)/submissions/(?P<pk>[0-9]+)/accept/', submission.SubmissionAccept.as_view(), name='submissions.accept'),
    url('^event/(?P<event>\w+)/submissions/(?P<pk>[0-9]+)/reject/', submission.SubmissionReject.as_view(), name='submissions.reject'),
    url('^event/(?P<event>\w+)/submissions/(?P<pk>[0-9]+)/edit/', submission.SubmissionUpdate.as_view(), name='submissions.edit'),
    url('^event/(?P<event>\w+)/submissions/(?P<pk>[0-9]+)/', submission.SubmissionDetail.as_view(), name='submissions.view'),
    url('^event/(?P<event>\w+)/submissions/', submission.SubmissionList.as_view(), name='submissions.list'),

    url('^event/(?P<event>\w+)/speakers/', speaker.SpeakerList.as_view(), name='speakers.list'),

    url('^event/(?P<event>\w+)/settings/edit/', settings.EventUpdate.as_view(), name='settings.event.edit'),
    url('^event/(?P<event>\w+)/settings/', settings.EventDetail.as_view(), name='settings.event.view'),

    url('^event/(?P<event>\w+)/$', dashboard.EventDashboardView.as_view(), name='event.dashboard'),
    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
]
