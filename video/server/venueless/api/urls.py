from django.urls import include, path, re_path
from rest_framework import routers

from . import views

world_router = routers.DefaultRouter()
world_router.register(r"rooms", views.RoomViewSet)

urlpatterns = [
    path("worlds/<str:world_id>/", views.WorldView.as_view(), name="root"),
    re_path("worlds/(?P<world_id>[^/]+)/schedule_update/?$", views.schedule_update),
    re_path("worlds/(?P<world_id>[^/]+)/delete_user/?$", views.delete_user),
    path("worlds/<str:world_id>/", include(world_router.urls)),
    path("worlds/<str:world_id>/theme", views.WorldThemeView.as_view()),
    path(
        "worlds/<str:world_id>/favourite-talk/",
        views.UserFavouriteView.as_view(),
    ),
    path("create-world/", views.CreateWorldView.as_view()),
    path("worlds/<str:world_id>/export-talk", views.ExportView.as_view()),
]
