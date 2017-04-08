from django.conf.urls import include, url

from .views import auth, cfp, dashboard, settings, speaker, submission

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),

    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
    url('^invitation/(?P<code>\w+)$', settings.InvitationView.as_view(), name='invitation.view'),
    url('^event/new$', settings.EventDetail.as_view(), name='event.create'),

    url('^event/(?P<event>\w+)/', include([
        url('^$', dashboard.EventDashboardView.as_view(), name='event.dashboard'),
        url('^cfp/questions$', cfp.CfPQuestionList.as_view(), name='cfp.questions.view'),
        url('^cfp/questions/new$', cfp.CfPQuestionDetail.as_view(), name='cfp.questions.create'),
        url('^cfp/questions/(?P<pk>[0-9]+)$', cfp.CfPQuestionDetail.as_view(), name='cfp.question.view'),
        url('^cfp/questions/(?P<pk>[0-9]+)/delete$', cfp.CfPQuestionDelete.as_view(), name='cfp.question.delete'),
        url('^cfp/questions/(?P<pk>[0-9]+)/edit$', cfp.CfPQuestionDetail.as_view(), name='cfp.question.edit'),
        url('^cfp/text$', cfp.CfPTextDetail.as_view(), name='cfp.text.view'),
        url('^cfp/text/edit$', cfp.CfPTextDetail.as_view(), name='cfp.text.edit'),
        url('^cfp/types$', cfp.SubmissionTypeList.as_view(), name='cfp.types.view'),
        url('^cfp/types/new$', cfp.SubmissionTypeDetail.as_view(), name='cfp.types.create'),
        url('^cfp/types/(?P<pk>[0-9]+)/delete$', cfp.SubmissionTypeDelete.as_view(), name='cfp.type.delete'),
        url('^cfp/types/(?P<pk>[0-9]+)/default$', cfp.SubmissionTypeDefault.as_view(), name='cfp.type.default'),
        url('^cfp/types/(?P<pk>[0-9]+)/edit$', cfp.SubmissionTypeDetail.as_view(), name='cfp.type.edit'),

        url('^submissions$', submission.SubmissionList.as_view(), name='submissions.list'),
        url('^submissions/(?P<pk>[0-9]+)/', include([
            url('^$', submission.SubmissionContent.as_view(), name='submissions.content.view'),
            url('^edit$', submission.SubmissionContent.as_view(), name='submissions.content.edit'),
            url('^accept$', submission.SubmissionAccept.as_view(), name='submissions.accept'),
            url('^reject$', submission.SubmissionReject.as_view(), name='submissions.reject'),
            url('^questions$', submission.SubmissionQuestions.as_view(), name='submissions.questions.view'),
            url('^questions/edit$', submission.SubmissionQuestions.as_view(), name='submissions.questions.edit'),
            url('^speakers$', submission.SubmissionSpeakers.as_view(), name='submissions.speakers.view'),
            url('^speakers/add$', submission.SubmissionSpeakersAdd.as_view(), name='submissions.speakers.add'),
            url('^speakers/delete$', submission.SubmissionSpeakersDelete.as_view(), name='submissions.speakers.delete'),
        ])),

        url('^speakers$', speaker.SpeakerList.as_view(), name='speakers.list'),
        url('^speakers/(?P<pk>[0-9]+)$', speaker.SpeakerDetail.as_view(), name='speakers.view'),
        url('^speakers/(?P<pk>[0-9]+)/edit$', speaker.SpeakerDetail.as_view(), name='speakers.edit'),

        url('^settings$', settings.EventDetail.as_view(), name='settings.event.view'),
        url('^settings/edit$', settings.EventDetail.as_view(), name='settings.event.edit'),
        url('^settings/team$', settings.EventTeam.as_view(), name='settings.team.view'),
        url('^settings/team/add$', settings.EventTeamInvite.as_view(), name='settings.team.add'),
        url('^settings/team/delete/(?P<pk>[0-9]+)$', settings.EventTeamDelete.as_view(), name='settings.team.delete'),
        url('^settings/team/retract/(?P<pk>[0-9]+)$', settings.EventTeamRetract.as_view(), name='settings.team.retract'),
    ])),
]
