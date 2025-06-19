from django.urls import path

from .views import linkedin, twitter

urlpatterns = [
    path("twitter/start", twitter.start_view, name="twitter.start"),
    path("twitter/return", twitter.return_view, name="twitter.return"),
    path("linkedin/start", linkedin.start_view, name="linkedin.start"),
    path("linkedin/return", linkedin.return_view, name="linkedin.return"),
]
