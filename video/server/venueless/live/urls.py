from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        "login/(?P<token>[a-zA-Z0-9]+)$",
        views.ShortTokenView.as_view(),
        name="token.short",
    ),
    re_path(
        "_feedback/$",
        views.FeedbackView.as_view(),
        name="feedback",
    ),
    re_path("_custom.css$", views.CustomCSSView.as_view(), name="css.custom"),
    re_path("_bbb.css$", views.BBBCSSView.as_view(), name="css.bbb"),
]
