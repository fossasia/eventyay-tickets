from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token

from pretalx.api.views import event, question, review, room, speaker, submission, user

default_router = routers.DefaultRouter()
default_router.register(r"events", event.EventViewSet)

event_router = routers.DefaultRouter()
event_router.register(r"submissions", submission.SubmissionViewSet)
event_router.register(r"talks", submission.SubmissionViewSet)
event_router.register(r"schedules", submission.ScheduleViewSet)
event_router.register(r"tags", submission.TagViewSet)
event_router.register(r"speakers", speaker.SpeakerViewSet)
event_router.register(r"reviews", review.ReviewViewSet)
event_router.register(r"rooms", room.RoomViewSet)
event_router.register(r"questions", question.QuestionViewSet)
event_router.register(r"answers", question.AnswerViewSet)

app_name = "api"
urlpatterns = [
    path("", include(default_router.urls)),
    path("me", user.MeView.as_view(), name="user.me"),
    path("auth/", obtain_auth_token),
    path("events/<event>/", include(event_router.urls)),
]
