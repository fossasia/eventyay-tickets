from django.urls import path

from . import views

app_name = "zoom"

urlpatterns = [
    path("meeting/", views.MeetingView.as_view(), name="meeting"),
    path("iframetest/", views.IframeTestView.as_view(), name="iframetest"),
    path("ended/", views.MeetingEndedView.as_view(), name="ended"),
]
