from django.urls import re_path

from . import views

urlpatterns = [
    re_path("custom.css$", views.CustomCSSView.as_view(), name="css.custom"),
]
