from django.urls import path

from . import views

urlpatterns = [
    path("<str:event_id>/upload/", views.UploadView.as_view(), name="upload"),
    path(
        "<str:event_id>/schedule_import/",
        views.ScheduleImportView.as_view(),
        name="schedule_import",
    ),
]
