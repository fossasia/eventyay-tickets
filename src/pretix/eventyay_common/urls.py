from django.urls import include, path, re_path as url

from pretix.eventyay_common.views import (
    account, dashboards, event, organizer, team,
)
from pretix.eventyay_common.views.orders import MyOrdersView

app_name = 'eventyay_common'

urlpatterns = [
    url(r'^$', dashboards.eventyay_common_dashboard, name='dashboard'),
    url(r'^widgets.json/$', dashboards.user_index_widgets_lazy, name='dashboard.widgets'),
    url(r'^organizers/$', organizer.OrganizerList.as_view(), name='organizers'),
    url(r'^organizers/add$', organizer.OrganizerCreate.as_view(), name='organizers.add'),
    url(r'^organizer/(?P<organizer>[^/]+)/update$', organizer.OrganizerUpdate.as_view(), name='organizer.update'),
    url(r'^organizer/(?P<organizer>[^/]+)/teams$', team.TeamListView.as_view(), name='organizer.teams'),
    url(r'^organizer/(?P<organizer>[^/]+)/team/add$', team.TeamCreateView.as_view(), name='organizer.team.add'),
    url(r'^organizer/(?P<organizer>[^/]+)/team/(?P<team>[^/]+)/edit$', team.TeamUpdateView.as_view(),
        name='organizer.team.edit'),
    url(r'^organizer/(?P<organizer>[^/]+)/team/(?P<team>[^/]+)/delete$', team.TeamDeleteView.as_view(),
        name='organizer.team.delete'),
    url(r'^events/$', event.EventList.as_view(), name='events'),
    url(r'^events/add$', event.EventCreateView.as_view(), name='events.add'),
    url(r'^event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/', include([
        url(r'^$', dashboards.EventIndexView.as_view(), name='event.index'),
        url(r'^widgets.json$', dashboards.event_index_widgets_lazy, name='event.index.widgets'),
        url(r'^settings/$', event.EventUpdate.as_view(), name='event.update'),
        url(r'^video-access/$', event.VideoAccessAuthenticator.as_view(), name='event.create_access_to_video'),
    ])),
    path('orders/', MyOrdersView.as_view(), name='orders'),
    url(r'^account/$', account.AccountSettings.as_view(), name='account'),
]
