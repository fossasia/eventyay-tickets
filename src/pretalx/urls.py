from contextlib import suppress

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static

from .agenda.urls import agenda_urls
from .cfp.urls import cfp_urls
from .orga.urls import orga_urls

urlpatterns = [
    url(r'^orga/', include(orga_urls, namespace='orga')),
    url(r'', include(agenda_urls, namespace='agenda')),
    url(r'', include(cfp_urls, namespace='cfp')),
]

if settings.DEBUG:
    with suppress(ImportError):
        import debug_toolbar
        urlpatterns += [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
