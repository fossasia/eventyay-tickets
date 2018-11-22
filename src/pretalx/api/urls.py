from django.conf.urls import include, url
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token

from pretalx.api.views import event, review, room, speaker, submission, user

default_router = routers.DefaultRouter()
default_router.register(r'events', event.EventViewSet)

event_router = routers.DefaultRouter()
event_router.register(r'submissions', submission.SubmissionViewSet)
event_router.register(r'talks', submission.TalkViewSet)
event_router.register(r'schedules', submission.ScheduleViewSet)
event_router.register(r'speakers', speaker.SpeakerViewSet)
event_router.register(r'reviews', review.ReviewViewSet)
event_router.register(r'rooms', room.RoomViewSet)

app_name = 'api'
urlpatterns = [
    url(r'^', include(default_router.urls)),
    url(r'^me$', user.MeView.as_view(), name='user.me'),
    url(r'^auth/', obtain_auth_token),
    url(r'^events/(?P<event>[^/]+)/', include(event_router.urls)),
]
