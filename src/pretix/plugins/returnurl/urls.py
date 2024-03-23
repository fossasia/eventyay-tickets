from django.urls import path

from .views import ReturnSettings

urlpatterns = [
    path('control/event/<str:organizer>/<str:event>/returnurl/settings',
        ReturnSettings.as_view(), name='settings'),
]
