from django.conf import settings
from django.urls import include, path
from django.urls import re_path as url
from django.views.generic import RedirectView

import pretix.control.urls
import pretix.eventyay_common.urls
import pretix.presale.urls
from pretix.base.views import js_helpers
from pretix.control.views import pages

from .base.views import cachedfiles, csp, health, js_catalog, metrics, redirect

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
    url(r'^api/v1/', include(('pretix.api.urls', 'pretixapi'), namespace='api-v1')),
    url(r'^api/$', RedirectView.as_view(url='/api/v1/'), name='redirect-api-version'),
    url(r'^accounts/', include('allauth.urls')),
]

control_patterns = [
    url(r'^control/', include((pretix.control.urls, 'control'))),
]

common_patterns = [
    url(r'^common/', include((pretix.eventyay_common.urls, 'common'))),
]

page_patterns = [
    path('page/<slug:slug>/', pages.ShowPageView.as_view(), name='page'),
]

debug_patterns = []
if settings.DEBUG:
    try:
        import debug_toolbar

        debug_patterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
    except ImportError:
        pass

common_patterns = base_patterns + control_patterns + debug_patterns + common_patterns + page_patterns
