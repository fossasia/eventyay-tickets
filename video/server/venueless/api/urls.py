from django.urls import include, re_path
from rest_framework import routers

from . import views

world_router = routers.DefaultRouter()
world_router.register(r"rooms", views.RoomViewSet)

urlpatterns = [
    re_path("worlds/(?P<world_id>[^/]+)/$", views.WorldView.as_view(), name="root"),
    re_path("worlds/(?P<world_id>[^/]+)/schedule_update/?$", views.schedule_update),
    re_path("worlds/(?P<world_id>[^/]+)/delete_user/?$", views.delete_user),
    re_path("worlds/(?P<world_id>[^/]+)/", include(world_router.urls)),
]
