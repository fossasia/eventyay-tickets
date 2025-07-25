from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


urlpatterns = [
    path('', admin.site.urls),
    # COMEBACK
    path(
        'users/impersonate/stop',
        lambda request: HttpResponse("<div>Please stop impersonating</div>"), 
        name='admin.users.impersonate.stop',
    ),
]
