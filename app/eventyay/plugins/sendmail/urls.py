from django.urls import path

from . import views

urlpatterns = [
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
        'control/event/<str:organizer>/<str:event>/sendmail/templates/',
        views.MailTemplatesView.as_view(),
        name='templates',
    ),
]
