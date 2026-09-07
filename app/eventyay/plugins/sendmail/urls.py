from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from . import views


urlpatterns = [
    path('mails/compose/', views.ComposeMailChoice.as_view(), name='event.mail.compose'),
    path('mails/compose/teams/', views.ComposeTeamsMail.as_view(), name='event.mail.compose_teams'),
    path('mails/attendees/select2/', views.attendees_select2, name='event.mail.attendees.select2'),
    path('mails/compose/attendees/recipients/', views.TicketMailRecipients.as_view(), name='event.mail.recipients'),
    path('mails/compose/teams/recipients/', views.TeamMailRecipients.as_view(), name='event.mail.teams.recipients'),
    path('mails/<int:pk>/', views.EditEmailQueueView.as_view(), name='event.mail.edit'),
    path('drafts/', views.DraftsListView.as_view(), name='event.mail.drafts'),
    path('drafts/duplicate/<int:pk>/', views.DuplicateDraftView.as_view(), name='event.mail.drafts.duplicate'),
    path('drafts/delete/<int:pk>/', views.DeleteEmailQueueView.as_view(), name='event.mail.drafts.delete'),
    path('drafts/purge/', views.PurgeDraftsView.as_view(), name='event.mail.drafts.purge'),
    path('outbox/', views.OutboxListView.as_view(), name='event.mail.outbox'),
    path('outbox/send/<int:pk>/', views.SendEmailQueueView.as_view(), name='event.mail.outbox.send'),
    path('outbox/delete/<int:pk>/', views.DeleteEmailQueueView.as_view(), name='event.mail.outbox.delete'),
    path('outbox/purge/', views.PurgeEmailQueuesView.as_view(), name='event.mail.outbox.purge'),
    path('sendmail/', views.SenderView.as_view(), name='event.mail.send'),
    path('sendmail/sent/', views.SentMailView.as_view(), name='event.mail.sent'),
    path('sendmail/templates/', views.MailTemplatesView.as_view(), name='event.mail.templates'),
]
