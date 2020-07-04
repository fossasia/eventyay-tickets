from django.urls import re_path

from . import views

urlpatterns = [
    re_path("upload/$", views.UploadView.as_view()),
]
