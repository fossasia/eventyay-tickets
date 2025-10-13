from django.urls import path, re_path

from .views import OrderPositionJoin, SettingsView

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/settings/venueless/',
        SettingsView.as_view(), name='settings'),
]
# Event-level URL patterns used by Eventyay's plugin loader
organizer_patterns = []

event_patterns = [
    re_path(
        r'^ticket/(?P<order>[^/]+)/(?P<position>\d+)/(?P<secret>[A-Za-z0-9]+)/(?P<view_schedule>True|False)/venueless/$',
        OrderPositionJoin.as_view(),
        name='join'),
]
