from django.urls import path

from . import views

urlpatterns = [
    path("upload/", views.UploadView.as_view(), name="upload"),
    path(
        "schedule_import/", views.ScheduleImportView.as_view(), name="schedule_import"
    ),
]
