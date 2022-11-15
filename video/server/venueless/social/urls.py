from django.urls import re_path

from .views import linkedin, twitter

urlpatterns = [
    re_path("twitter/start$", twitter.start_view, name="twitter.start"),
    re_path("twitter/return$", twitter.return_view, name="twitter.return"),
    re_path("linkedin/start$", linkedin.start_view, name="linkedin.start"),
    re_path("linkedin/return$", linkedin.return_view, name="linkedin.return"),
]
