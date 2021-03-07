from django.urls import re_path

from . import views

urlpatterns = [
    re_path("upload/$", views.UploadView.as_view(), name="upload"),
    re_path(
        "schedule_import/$", views.ScheduleImportView.as_view(), name="schedule_import"
    ),
]
