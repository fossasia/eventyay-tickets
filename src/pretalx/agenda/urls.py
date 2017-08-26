from django.conf.urls import url

from .views import feed, location, schedule, speaker

agenda_urls = [
    url('^(?P<event>\w+)/schedule/$', schedule.ScheduleView.as_view(), name='schedule'),
    url('^(?P<event>\w+)/schedule/changelog$', schedule.ChangelogView.as_view(), name='schedule.changelog'),
    url('^(?P<event>\w+)/schedule.xml$', schedule.FrabXmlView.as_view(), name='frab-xml'),
    url('^(?P<event>\w+)/schedule.xcal$', schedule.FrabXCalView.as_view(), name='frab-xcal'),
    url('^(?P<event>\w+)/schedule.json$', schedule.FrabJsonView.as_view(), name='frab-json'),
    url('^(?P<event>\w+)/schedule.ics$', schedule.ICalView.as_view(), name='ical'),
    url('^(?P<event>\w+)/schedule/feed.xml$', feed.ScheduleFeed(), name='feed'),

    url('^(?P<event>\w+)/location/$', location.LocationView.as_view(), name='location'),
    url('^(?P<event>\w+)/talk/(?P<slug>\w+)/$', schedule.TalkView.as_view(), name='talk'),
    url('^(?P<event>\w+)/speaker/(?P<name>\w+)/$', speaker.SpeakerView.as_view(), name='speaker'),
]
