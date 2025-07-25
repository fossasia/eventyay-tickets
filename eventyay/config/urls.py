from django.contrib import admin
from django.urls import re_path as url
from django.urls import include, path

import eventyay.control.urls

from eventyay.base.views import health
base_patterns = [
    url(r'^healthcheck/$', health.healthcheck, name='healthcheck'),
]
control_patterns = [
    url(r'^control/', include((eventyay.control.urls, 'control'))),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    *base_patterns,
    *control_patterns,
]
