from django.urls import re_path

from . import views

urlpatterns = [
    re_path("_custom.css$", views.CustomCSSView.as_view(), name="css.custom"),
    re_path("_bbb.css$", views.BBBCSSView.as_view(), name="css.bbb"),
]
