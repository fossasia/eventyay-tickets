from django.urls import re_path as url

from .views import IndexView

urlpatterns = [
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/webcheckin/$',
        IndexView.as_view(), name='index'),
]
