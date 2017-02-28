from django.conf import settings
from django.conf.urls import include, url

from .orga.urls import orga_urls
from .cfp.urls import cfp_urls

urlpatterns = [
    url(r'^orga/', include(orga_urls, namespace='orga')),
    url(r'', include(cfp_urls, namespace='cfp')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
