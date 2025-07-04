from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/world/<str:world>/", consumers.MainConsumer.as_asgi()),
]
