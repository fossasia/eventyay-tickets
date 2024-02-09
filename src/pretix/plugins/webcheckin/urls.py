from django.conf.urls import re_path

from .views import IndexView

urlpatterns = [
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/webcheckin/$',
        IndexView.as_view(), name='index'),
]
