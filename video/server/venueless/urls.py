from django.urls import re_path

from .live import views

urlpatterns = [
    re_path(r"(.*)", views.AppView.as_view()),
]
