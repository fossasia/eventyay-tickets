from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/world/(?P<world>[^/]+)/$", consumers.MainConsumer.as_asgi()),
]
