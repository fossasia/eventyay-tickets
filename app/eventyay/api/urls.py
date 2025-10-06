from django.urls import include, path, re_path
from rest_framework import routers

# Import views directly from their modules to avoid relying on package attribute access
from .views.rooms import RoomViewSet
from .views.event import (
    EventView,
    schedule_update,
    delete_user,
    EventThemeView,
    UserFavouriteView,
    CreateEventView,
    ExportView,
)

orga_router = routers.DefaultRouter(trailing_slash=False)

event_router = routers.DefaultRouter(trailing_slash=False)
event_router.register(r"rooms", RoomViewSet)

router = routers.DefaultRouter(trailing_slash=False)
urlpatterns = [
    path("events/<str:event_id>/", EventView.as_view(), name="root"),
    re_path("events/(?P<event_id>[^/]+)/schedule_update/?$", schedule_update),
    re_path("events/(?P<event_id>[^/]+)/delete_user/?$", delete_user),
    path("events/<str:event_id>/", include(event_router.urls)),
    path("events/<str:event_id>/theme", EventThemeView.as_view()),
    path(
        "events/<str:event_id>/favourite-talk/",
        UserFavouriteView.as_view(),
    ),
    path("create-event/", CreateEventView.as_view()),
    path("events/<str:event_id>/export-talk", ExportView.as_view()),
]

