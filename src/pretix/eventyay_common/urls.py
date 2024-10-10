from django.urls import re_path as url, include

from pretix.eventyay_common.views import dashboards, event, organizer, team

app_name = 'eventyay_common'

urlpatterns = [
    url(r'^$', dashboards.organiser_dashboard, name='dashboard'),
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
        url(r'^settings/$', event.EventUpdate.as_view(), name='event.update'),
        url('', event.VideoAccessAuthenticator.as_view(), name='event.create_access_to_video'),
    ])),
]
