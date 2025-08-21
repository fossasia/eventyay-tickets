from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from django.urls import include, path
from django.urls import reverse, re_path as url
from django.utils.html import escape
from django.utils.translation import gettext as _

from django.http import HttpResponse



import eventyay.control.urls
import eventyay.eventyay_common.urls
import eventyay.exhibitors.urls

from eventyay.base.views import health


def blank_view(request):
    index_url = reverse('eventyay_common:dashboard')
    content = _(
        '<a href="%(url)s">Click to login here</a>.'
    ) % {'url': escape(index_url)}

    return HttpResponse(f"<p>{content}</p>")


base_patterns = [
    url(r'^healthcheck/$', health.healthcheck, name='healthcheck'),
    url(r'^csp_report/$', health.csp_report, name='csp_report'),
    url(r'^tickets/csp_report/$', health.csp_report, name='tickets_csp_report'),
]

control_patterns = [
    url(r'^control/', include((eventyay.control.urls, 'control'))),
]

common_patterns = [
    url(r'^common/', include((eventyay.eventyay_common.urls, 'common'))),
]

exhibitor_patterns = [
    url(r'^exhibitors/', include((eventyay.exhibitors.urls, 'exhibitors'))),
    url(r'^api/exhibitors/', include(eventyay.exhibitors.urls.api_patterns)),
]

admin_patterns = [
    path('admin/', include('eventyay.config.urls_admin')),
]

urlpatterns = [
    *admin_patterns,
    *base_patterns,
    *control_patterns,
    *common_patterns,
    *exhibitor_patterns,

    path('', blank_view, name='blank'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
