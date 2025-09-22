import importlib.util

from django.conf import settings
from django.urls import include, path
from django.urls import re_path as url

import eventyay.control.urls
import eventyay.eventyay_common.urls
import eventyay.presale.urls
from eventyay.base.views import cachedfiles, csp, health, js_catalog, js_helpers, metrics, redirect
from eventyay.control.views import pages


base_patterns = [
    url(
        r'^download/(?P<id>[^/]+)/$',
        cachedfiles.DownloadView.as_view(),
        name='cachedfile.download',
    ),
    url(r'^healthcheck/$', health.healthcheck, name='healthcheck'),
    url(r'^redirect/$', redirect.redir_view, name='redirect'),
    url(
        r'^jsi18n/(?P<lang>[a-zA-Z-_]+)/$',
        js_catalog.js_catalog,
        name='javascript-catalog',
    ),
    url(r'^metrics$', metrics.serve_metrics, name='metrics'),
    url(r'^csp_report/$', csp.csp_report, name='csp.report'),
    url(r'^js_helpers/states/$', js_helpers.states, name='js_helpers.states'),
    # url(r'^api/v1/', include(('eventyay.api.urls', 'eventyayapi'), namespace='api-v1')),
    # url(r'^api/$', RedirectView.as_view(url='/api/v1/'), name='redirect-api-version'),
    url(r'^accounts/', include('allauth.urls')),
]

control_patterns = [
    url(r'^control/', include((eventyay.control.urls, 'control'))),
]

common_patterns = [
    url(r'^common/', include((eventyay.eventyay_common.urls, 'common'), namespace='common')),
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

common_patterns = base_patterns + control_patterns + debug_patterns + common_patterns + page_patterns + admin_patterns
