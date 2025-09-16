import importlib

from django.apps import apps
from django.urls import include
from django.urls import re_path as url
from rest_framework import routers

router = routers.DefaultRouter(trailing_slash=False)

orga_router = routers.DefaultRouter(trailing_slash=False)

event_router = routers.DefaultRouter(trailing_slash=False)
