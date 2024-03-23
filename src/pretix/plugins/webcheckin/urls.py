from django.urls import path

from .views import IndexView

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/webcheckin/',
        IndexView.as_view(), name='index'),
]
