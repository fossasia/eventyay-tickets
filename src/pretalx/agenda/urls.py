from django.conf.urls import include, url

from pretalx.event.models.event import SLUG_CHARS

from .views import feed, location, schedule, speaker, talk

app_name = 'agenda'
urlpatterns = [
    url(f'^(?P<event>[{SLUG_CHARS}]+)/', include([
        url('^schedule/$', schedule.ScheduleView.as_view(), name='schedule'),
        url('^schedule/changelog$', schedule.ChangelogView.as_view(), name='schedule.changelog'),
        url('^schedule.xml$', schedule.FrabXmlView.as_view(), name='frab-xml'),
        url('^schedule.xcal$', schedule.FrabXCalView.as_view(), name='frab-xcal'),
        url('^schedule.json$', schedule.FrabJsonView.as_view(), name='frab-json'),
        url('^schedule.ics$', schedule.ICalView.as_view(), name='ical'),
        url('^schedule/feed.xml$', feed.ScheduleFeed(), name='feed'),

        url('^location/$', location.LocationView.as_view(), name='location'),
        url('^talk/(?P<slug>\w+)/$', talk.TalkView.as_view(), name='talk'),
        url('^talk/(?P<slug>\w+)/feedback/$', talk.FeedbackView.as_view(), name='feedback'),
        url('^talk/(?P<slug>\w+)/ical/$', talk.SingleICalView.as_view(), name='ical'),
        url('^speaker/(?P<code>\w+)/$', speaker.SpeakerView.as_view(), name='speaker'),
    ])),
]
