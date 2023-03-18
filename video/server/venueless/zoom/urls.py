from django.urls import re_path

from . import views

urlpatterns = [
    re_path("meeting/$", views.MeetingView.as_view(), name="meeting"),
    re_path("iframetest/$", views.IframeTestView.as_view(), name="iframetest"),
    re_path("ended/$", views.MeetingEndedView.as_view(), name="ended"),
]
