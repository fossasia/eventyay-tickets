from django.conf.urls import include, url
from rest_framework import routers

from pretalx.api.views import event, speaker, submission


default_router = routers.DefaultRouter()
default_router.register(r'events', event.EventViewSet)

event_router = routers.DefaultRouter()
event_router.register(r'submitters', speaker.SubmitterViewSet)
event_router.register(r'speakers', speaker.SubmitterViewSet)
event_router.register(r'submissions', submission.SubmissionViewSet)
event_router.register(r'talks', submission.SubmissionViewSet)
event_router.register(r'schedules', submission.ScheduleViewSet)

api_urls = [
    url(r'^', include(default_router.urls)),
    url(r'^events/(?P<event>[^/]+)/', include(event_router.urls)),
]
