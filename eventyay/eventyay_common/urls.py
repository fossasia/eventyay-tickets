from django.http import HttpResponse
from django.urls import path

app_name = 'eventyay_common'

urlpatterns = [
    path('', lambda request: HttpResponse("<div>This is a common dashboard page</div>"), name='dashboard'),
]
