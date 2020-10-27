from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        "attendance.(?P<type>(svg|png|pdf))$", views.RoomAttendanceGraphView.as_view()
    ),
    re_path("report.(?P<type>(pdf))$", views.ReportView.as_view()),
]
