from django.conf.urls import url

from .views import location, schedule, speaker

agenda_urls = [
    url('^(?P<event>\w+)/schedule/$', schedule.ScheduleView.as_view(), name='schedule'),
    url('^(?P<event>\w+)/schedule.xml$', schedule.FrabView.as_view(), name='frab'),

    url('^(?P<event>\w+)/location/$', location.LocationView.as_view(), name='location'),
    url('^(?P<event>\w+)/talk/(?P<pk>[0-9]+)/$', schedule.TalkView.as_view(), name='talk'),
    url('^(?P<event>\w+)/speaker/(?P<name>\w+)/$', speaker.SpeakerView.as_view(), name='speaker'),
]
