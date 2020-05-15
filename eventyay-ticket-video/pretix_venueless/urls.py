from django.conf.urls import url

from .views import (
    OrderPositionJoin, SettingsView
)

urlpatterns = [
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/settings/venueless/$',
        SettingsView.as_view(), name='settings'),
]
event_patterns = [
    url(
        r'^ticket/(?P<order>[^/]+)/(?P<position>\d+)/(?P<secret>[A-Za-z0-9]+)/venueless/$',
        OrderPositionJoin.as_view(),
        name='join'),
]
