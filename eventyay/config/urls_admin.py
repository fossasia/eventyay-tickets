from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


urlpatterns = [
    path('', admin.site.urls),
]
