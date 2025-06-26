from django.http import HttpResponsePermanentRedirect
from django.urls import include, path
from rest_framework import routers

from pretalx.api.views import (
    access_code,
    event,
    mail,
    question,
    review,
    room,
    schedule,
    speaker,
    speaker_information,
    submission,
    team,
    upload,
)


def talks_to_submissions_redirect(request, event, subpath):
    """
    Redirects requests from /events/.../talks/... to /events/.../submissions/...
    preserving the subpath and query parameters.
    """
    new_path = request.path.replace("/talks/", "/submissions/", 1)

    query_string = request.META.get("QUERY_STRING", "")
    if query_string:
        new_path += "?" + query_string

    return HttpResponsePermanentRedirect(new_path)


default_router = routers.SimpleRouter()
default_router.register("events", event.EventViewSet, basename="event")

event_router = routers.SimpleRouter()
event_router.register(
    "submissions", submission.SubmissionViewSet, basename="submission"
)
event_router.register("schedules", schedule.ScheduleViewSet, basename="schedule")
event_router.register("slots", schedule.TalkSlotViewSet, basename="slots")
event_router.register("tags", submission.TagViewSet, basename="tag")
event_router.register(
    "submission-types", submission.SubmissionTypeViewSet, basename="submission_type"
)
event_router.register("tracks", submission.TrackViewSet, basename="track")
event_router.register(
    "mail-templates", mail.MailTemplateViewSet, basename="mail_template"
)
event_router.register(
    "access-codes", access_code.SubmitterAccessCodeViewSet, basename="access_code"
)
event_router.register("speakers", speaker.SpeakerViewSet, basename="speaker")
event_router.register("reviews", review.ReviewViewSet, basename="review")
event_router.register("rooms", room.RoomViewSet, basename="room")
event_router.register("questions", question.QuestionViewSet, basename="question")
event_router.register("answers", question.AnswerViewSet, basename="answer")
event_router.register(
    "question-options", question.AnswerOptionViewSet, basename="question_option"
)
event_router.register(
    "speaker-information",
    speaker_information.SpeakerInformationViewSet,
    basename="speaker_information",
)

organiser_router = routers.DefaultRouter()
organiser_router.register("teams", team.TeamViewSet, basename="team")


app_name = "api"
urlpatterns = [
    path("", include(default_router.urls)),
    # We redirect the old pre-filtered /talks/ endpoint to  /submissions/
    path(
        "events/<slug:event>/talks/<path:subpath>",
        talks_to_submissions_redirect,
        name="event_talks_redirect",
    ),
    # The favourites endpoints are separate, as they are functions, not viewsets.
    # They need to be separate from the viewset in order to permit session
    # authentication.
    path(
        "events/<slug:event>/submissions/favourites/",
        submission.favourites_view,
        name="submission.favourites",
    ),
    path(
        "events/<slug:event>/submissions/<slug:code>/favourite/",
        submission.favourite_view,
        name="submission.favourite",
    ),
    path("upload/", upload.UploadView.as_view(), name="upload"),
    path("events/<slug:event>/", include(event_router.urls)),
    path(
        "events/<slug:event>/favourite-talk/",
        submission.SubmissionFavouriteDeprecatedView.as_view(),
    ),
    path("configure-video-settings/", event.ConfigureVideoSettingsView.as_view()),
    path("organisers/<slug:organiser>/", include(organiser_router.urls)),
]
