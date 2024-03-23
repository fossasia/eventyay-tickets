from django.urls import path, re_path

from . import views

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/sendmail/', views.SenderView.as_view(),
        name='send'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sendmail/history/', views.EmailHistoryView.as_view(), name='history')
]
