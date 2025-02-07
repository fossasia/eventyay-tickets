from django.urls import re_path as url

from . import views

urlpatterns = [
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/statistics/', views.IndexView.as_view(),
        name='index'),
]
