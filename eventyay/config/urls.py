from django.contrib import admin
from django.urls import include, path
from django.urls import re_path as url

from django.http import HttpResponse

from eventyay.eventyay_common.views import auth

import eventyay.control.urls
import eventyay.eventyay_common.urls

from eventyay.base.views import health

base_patterns = [
    url(r'^healthcheck/$', health.healthcheck, name='healthcheck'),
]

control_patterns = [
    url(r'^control/', include((eventyay.control.urls, 'control'))),
]

common_patterns = [
    url(r'^common/', include((eventyay.eventyay_common.urls, 'common'))),
]

admin_patterns = [
    path('admin/', include('config.urls_admin')),
]

urlpatterns = [
    *admin_patterns,
    *base_patterns,
    *control_patterns,
    *common_patterns,

    path('', lambda request: HttpResponse("<div>This is a blank page"), name='blank'),
]
