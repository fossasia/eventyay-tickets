from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token

from pretalx.api.views import event, question, review, room, speaker, submission, user

default_router = routers.DefaultRouter()
default_router.register(r"events", event.EventViewSet, basename="event")

event_router = routers.DefaultRouter()
event_router.register(
    r"submissions", submission.SubmissionViewSet, basename="submission"
)
event_router.register(r"talks", submission.SubmissionViewSet, basename="talks")
event_router.register(r"schedules", submission.ScheduleViewSet, basename="schedule")
event_router.register(r"tags", submission.TagViewSet, basename="tag")
event_router.register(r"speakers", speaker.SpeakerViewSet, basename="speaker")
event_router.register(r"reviews", review.ReviewViewSet, basename="review")
event_router.register(r"rooms", room.RoomViewSet, basename="room")
event_router.register(r"questions", question.QuestionViewSet, basename="question")
event_router.register(r"answers", question.AnswerViewSet, basename="answer")

app_name = "api"
urlpatterns = [
    path("", include(default_router.urls)),
    path("me", user.MeView.as_view(), name="user.me"),
    path("auth/", obtain_auth_token),
    path("events/<event>/", include(event_router.urls)),
]
