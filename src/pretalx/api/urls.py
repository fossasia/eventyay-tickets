from django.conf.urls import include, url
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token

from pretalx.api.views import event, speaker, submission

default_router = routers.DefaultRouter()
default_router.register(r'events', event.EventViewSet)

event_router = routers.DefaultRouter()
event_router.register(r'submissions', submission.SubmissionViewSet)
event_router.register(r'talks', submission.SubmissionViewSet)
event_router.register(r'schedules', submission.ScheduleViewSet)
event_router.register(r'speakers', speaker.SpeakerViewSet)

app_name = 'api'
urlpatterns = [
    url(r'^', include(default_router.urls)),
    url(r'^auth/', obtain_auth_token),
    url(r'^events/(?P<event>[^/]+)/', include(event_router.urls)),
]
