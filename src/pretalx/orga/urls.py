from django.conf.urls import include, url

from pretalx.event.models.event import SLUG_CHARS
from pretalx.orga.views import cards

from .views import (
    auth, cfp, dashboard, event, mails, person,
    review, schedule, speaker, submission,
)

orga_urls = [
    url('^login/$', auth.LoginView.as_view(), name='login'),
    url('^logout/$', auth.logout_view, name='logout'),

    url('^$', dashboard.DashboardView.as_view(), name='dashboard'),
    url('^me$', event.UserSettings.as_view(), name='user.view'),
    url('^invitation/(?P<code>\w+)$', event.InvitationView.as_view(), name='invitation.view'),
    url('^event/new/$', event.EventDetail.as_view(), name='event.create'),

    url(f'^event/(?P<event>[{SLUG_CHARS}]+)/', include([
        url('^$', dashboard.EventDashboardView.as_view(), name='event.dashboard'),
        url('^users$', person.UserList.as_view(), name='event.user_list'),

        url('^cfp/questions$', cfp.CfPQuestionList.as_view(), name='cfp.questions.view'),
        url('^cfp/questions/new$', cfp.CfPQuestionDetail.as_view(), name='cfp.questions.create'),
        url('^cfp/questions/(?P<pk>[0-9]+)$', cfp.CfPQuestionDetail.as_view(), name='cfp.question.view'),
        url('^cfp/questions/(?P<pk>[0-9]+)/delete$', cfp.CfPQuestionDelete.as_view(), name='cfp.question.delete'),
        url('^cfp/questions/(?P<pk>[0-9]+)/edit$', cfp.CfPQuestionDetail.as_view(), name='cfp.question.edit'),
        url('^cfp/questions/(?P<pk>[0-9]+)/toggle$', cfp.CfPQuestionToggle.as_view(), name='cfp.question.toggle'),
        url('^cfp/text$', cfp.CfPTextDetail.as_view(), name='cfp.text.view'),
        url('^cfp/text/edit$', cfp.CfPTextDetail.as_view(), name='cfp.text.edit'),
        url('^cfp/types$', cfp.SubmissionTypeList.as_view(), name='cfp.types.view'),
        url('^cfp/types/new$', cfp.SubmissionTypeDetail.as_view(), name='cfp.types.create'),
        url('^cfp/types/(?P<pk>[0-9]+)/delete$', cfp.SubmissionTypeDelete.as_view(), name='cfp.type.delete'),
        url('^cfp/types/(?P<pk>[0-9]+)/default$', cfp.SubmissionTypeDefault.as_view(), name='cfp.type.default'),
        url('^cfp/types/(?P<pk>[0-9]+)/edit$', cfp.SubmissionTypeDetail.as_view(), name='cfp.type.edit'),

        url('^mails/', include([
            url('^(?P<pk>[0-9]+)$', mails.MailDetail.as_view(), name='mails.outbox.mail.view'),
            url('^(?P<pk>[0-9]+)/edit$', mails.MailDetail.as_view(), name='mails.outbox.mail.edit'),
            url('^(?P<pk>[0-9]+)/copy$', mails.MailCopy.as_view(), name='mails.outbox.mail.copy'),
            url('^(?P<pk>[0-9]+)/delete$', mails.OutboxPurge.as_view(), name='mails.outbox.mail.delete'),
            url('^(?P<pk>[0-9]+)/send$', mails.OutboxSend.as_view(), name='mails.outbox.mail.send'),
            url('^templates$', mails.TemplateList.as_view(), name='mails.templates.list'),
            url('^templates/new$', mails.TemplateDetail.as_view(), name='mails.templates.create'),
            url('^templates/(?P<pk>[0-9]+)/edit$', mails.TemplateDetail.as_view(), name='mails.templates.edit'),
            url('^templates/(?P<pk>[0-9]+)/delete$', mails.TemplateDelete.as_view(), name='mails.templates.delete'),
            url('^send$', mails.SendMail.as_view(), name='mails.send'),
            url('^sent$', mails.SentMail.as_view(), name='mails.sent'),
            url('^outbox$', mails.OutboxList.as_view(), name='mails.outbox.list'),
            url('^outbox/send$', mails.OutboxSend.as_view(), name='mails.outbox.send'),
            url('^outbox/purge$', mails.OutboxPurge.as_view(), name='mails.outbox.purge'),
        ])),

        url('^submissions$', submission.SubmissionList.as_view(), name='submissions.list'),
        url('^submissions/new$', submission.SubmissionContent.as_view(), name='submissions.create'),
        url('^submissions/cards/$', cards.SubmissionCards.as_view(), name='submissions.cards'),
        url('^submissions/(?P<code>\w+)/', include([
            url('^$', submission.SubmissionContent.as_view(), name='submissions.content.view'),
            url('^edit$', submission.SubmissionContent.as_view(), name='submissions.content.edit'),
            url('^accept$', submission.SubmissionAccept.as_view(), name='submissions.accept'),
            url('^reject$', submission.SubmissionReject.as_view(), name='submissions.reject'),
            url('^confirm', submission.SubmissionConfirm.as_view(), name='submissions.confirm'),
            url('^unconfirm', submission.SubmissionUnconfirm.as_view(), name='submissions.unconfirm'),
            url('^delete', submission.SubmissionDelete.as_view(), name='submissions.delete'),
            url('^questions$', submission.SubmissionQuestions.as_view(), name='submissions.questions.view'),
            url('^questions/edit$', submission.SubmissionQuestions.as_view(), name='submissions.questions.edit'),
            url('^speakers$', submission.SubmissionSpeakers.as_view(), name='submissions.speakers.view'),
            url('^speakers/add$', submission.SubmissionSpeakersAdd.as_view(), name='submissions.speakers.add'),
            url('^speakers/delete$', submission.SubmissionSpeakersDelete.as_view(), name='submissions.speakers.delete'),
            url('^reviews$', review.ReviewSubmission.as_view(), name='submissions.reviews'),
            url('^reviews/delete$', review.ReviewSubmissionDelete.as_view(), name='submissions.reviews.submission.delete'),
            url('^feedback/$', submission.FeedbackList.as_view(), name='submissions.feedback.list'),
        ])),

        url('^speakers$', speaker.SpeakerList.as_view(), name='speakers.list'),
        url('^speakers/(?P<pk>[0-9]+)$', speaker.SpeakerDetail.as_view(), name='speakers.view'),
        url('^speakers/(?P<pk>[0-9]+)/edit$', speaker.SpeakerDetail.as_view(), name='speakers.edit'),

        url('^reviews$', review.ReviewDashboard.as_view(), name='reviews.dashboard'),

        url('^settings$', event.EventDetail.as_view(), name='settings.event.view'),
        url('^settings/edit$', event.EventDetail.as_view(), name='settings.event.edit'),
        url('^settings/mail$', event.EventMailSettings.as_view(), name='settings.mail.view'),
        url('^settings/mail/edit$', event.EventMailSettings.as_view(), name='settings.mail.edit'),
        url('^settings/team$', event.EventTeam.as_view(), name='settings.team.view'),
        url('^settings/team/add$', event.EventTeamInvite.as_view(), name='settings.team.add'),
        url('^settings/team/delete/(?P<pk>[0-9]+)$', event.EventTeamDelete.as_view(), name='settings.team.delete'),
        url('^settings/team/retract/(?P<pk>[0-9]+)$', event.EventTeamRetract.as_view(), name='settings.team.retract'),
        url('^settings/reviews$', event.EventReview.as_view(), name='settings.review.view'),
        url('^settings/reviews/add$', event.EventReviewInvite.as_view(), name='settings.review.add'),
        url('^settings/reviews/delete/(?P<pk>[0-9]+)$', event.EventReviewDelete.as_view(), name='settings.review.delete'),
        url('^settings/reviews/retract/(?P<pk>[0-9]+)$', event.EventReviewRetract.as_view(), name='settings.review.retract'),
        url('^settings/rooms$', event.RoomList.as_view(), name='settings.rooms.list'),
        url('^settings/rooms/new$', event.RoomDetail.as_view(), name='settings.rooms.create'),
        url('^settings/rooms/(?P<pk>[0-9]+)$', event.RoomDetail.as_view(), name='settings.rooms.view'),
        url('^settings/rooms/(?P<pk>[0-9]+)/edit$', event.RoomDetail.as_view(), name='settings.rooms.edit'),
        url('^settings/rooms/(?P<pk>[0-9]+)/delete$', event.RoomDelete.as_view(), name='settings.rooms.delete'),

        url('^schedule/$', schedule.ScheduleView.as_view(), name='schedule.main'),
        url('^schedule/release$', schedule.ScheduleReleaseView.as_view(), name='schedule.release'),
        url('^schedule/reset$', schedule.ScheduleResetView.as_view(), name='schedule.reset'),
        url('^schedule/toggle$', schedule.ScheduleToggleView.as_view(), name='schedule.toggle'),
        url('^schedule/api/rooms/$', schedule.RoomList.as_view(), name='schedule.api.rooms'),
        url('^schedule/api/talks/$', schedule.TalkList.as_view(), name='schedule.api.talks'),
        url('^schedule/api/talks/(?P<pk>[0-9]+)/$', schedule.TalkUpdate.as_view(), name='schedule.api.update'),
        url(
            '^schedule/api/availabilities/(?P<talkid>[0-9]+)/(?P<roomid>[0-9]+)/$',
            schedule.RoomTalkAvailabilities.as_view(), name='schedule.api.availabilities'
        ),
    ])),
]
