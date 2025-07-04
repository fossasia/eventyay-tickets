from django.urls import path

from . import views

urlpatterns = [
    path(
        'control/event/<str:organizer>/<str:event>/mails/compose/', 
        views.ComposeMailChoice.as_view(), 
        name='compose_email_choice'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/outbox/',
        views.OutboxListView.as_view(),
        name='outbox',
    ),
    path(
        'control/event/<str:organizer>/<str:event>/outbox/send/<int:pk>/', 
        views.SendQueuedMailView.as_view(), 
        name='send_single'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/mails/<int:pk>/', 
        views.EditQueuedMailView.as_view(), 
        name='edit_mail'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/outbox/delete/<int:pk>/', 
        views.DeleteQueuedMailView.as_view(), 
        name='delete_single'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/outbox/purge/', 
        views.PurgeQueuedMailsView.as_view(), 
        name='purge_all'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/sendmail/',
        views.SenderView.as_view(),
        name='send',
    ),
    path(
        'control/event/<str:organizer>/<str:event>/sendmail/history/',
        views.EmailHistoryView.as_view(),
        name='history',
    ),
    path(
        'control/event/<str:organizer>/<str:event>/sendmail/sent/',
        views.SentMailView.as_view(),
        name='sent',
    ),
    path(
        'control/event/<str:organizer>/<str:event>/sendmail/templates/',
        views.MailTemplatesView.as_view(),
        name='templates',
    ),
]
