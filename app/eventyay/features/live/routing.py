from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/event/<str:event>/", consumers.MainConsumer.as_asgi()),
]
