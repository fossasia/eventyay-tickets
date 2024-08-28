from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token

from pretalx.api.views import event, question, review, room, speaker, submission, user

default_router = routers.DefaultRouter()
default_router.register("events", event.EventViewSet, basename="event")

event_router = routers.DefaultRouter()
event_router.register(
    "submissions", submission.SubmissionViewSet, basename="submission"
)
event_router.register("talks", submission.SubmissionViewSet, basename="talks")
event_router.register("schedules", submission.ScheduleViewSet, basename="schedule")
event_router.register("tags", submission.TagViewSet, basename="tag")
event_router.register("speakers", speaker.SpeakerViewSet, basename="speaker")
event_router.register("reviews", review.ReviewViewSet, basename="review")
event_router.register("rooms", room.RoomViewSet, basename="room")
event_router.register("questions", question.QuestionViewSet, basename="question")
event_router.register("answers", question.AnswerViewSet, basename="answer")

app_name = "api"
urlpatterns = [
    path("", include(default_router.urls)),
    path("me", user.MeView.as_view(), name="user.me"),
    path("auth/", obtain_auth_token),
    path("events/<event>/", include(event_router.urls)),
    path(
        "events/<event>/favourite-talk/", submission.SubmissionFavouriteView.as_view()
    ),
]
