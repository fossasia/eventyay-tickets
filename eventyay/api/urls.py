from django.urls import include, path, re_path
from rest_framework import routers

from . import views

event_router = routers.DefaultRouter()
event_router.register(r"rooms", views.rooms.RoomViewSet)

urlpatterns = [
    path("events/<str:event_id>/", views.EventView.as_view(), name="root"),
    re_path("events/(?P<event_id>[^/]+)/schedule_update/?$", views.schedule_update),
    re_path("events/(?P<event_id>[^/]+)/delete_user/?$", views.delete_user),
    path("events/<str:event_id>/", include(event_router.urls)),
    path("events/<str:event_id>/theme", views.EventThemeView.as_view()),
    path(
        "events/<str:event_id>/favourite-talk/",
        views.UserFavouriteView.as_view(),
    ),
    path("create-event/", views.CreateEventView.as_view()),
    path("events/<str:event_id>/export-talk", views.ExportView.as_view()),
]
