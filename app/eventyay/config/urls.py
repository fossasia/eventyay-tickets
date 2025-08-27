import importlib.util

from django.conf import settings
from django.urls import include, path
from django.urls import re_path as url

import eventyay.control.urls
import eventyay.eventyay_common.urls
import eventyay.presale.urls
from eventyay.base.views import health
from eventyay.control.views import pages

base_patterns = [
    url(r'^healthcheck/$', health.healthcheck, name='healthcheck'),
]

control_patterns = [
    url(r'^control/', include((eventyay.control.urls, 'control'))),
]

eventyay_common_patterns = [
    path('', include((eventyay.eventyay_common.urls, 'common'))),
]


page_patterns = [
    path('page/<slug:slug>/', pages.ShowPageView.as_view(), name='page'),
]

admin_patterns = [
    path('admin/', include('eventyay.config.urls_admin')),
]

debug_patterns = []

if settings.DEBUG and importlib.util.find_spec('debug_toolbar'):
    debug_patterns.append(path('__debug__/', include('debug_toolbar.urls')))

common_patterns = (
    base_patterns + control_patterns + debug_patterns + eventyay_common_patterns + page_patterns + admin_patterns
)
