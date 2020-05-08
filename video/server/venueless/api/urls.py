from django.urls import include, re_path
from rest_framework import routers

from . import views

world_router = routers.DefaultRouter()
world_router.register(r"rooms", views.RoomViewSet)

urlpatterns = [
    re_path("worlds/(?P<world_id>[^/]+)/$", views.WorldView.as_view()),
    re_path("worlds/(?P<world_id>[^/]+)/", include(world_router.urls)),
]
