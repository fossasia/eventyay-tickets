from contextlib import suppress

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static


urlpatterns = [
    url(r'^orga/', include('pretalx.orga.urls', namespace='orga')),
    url(r'^api/', include('pretalx.api.urls', namespace='api')),
    url(r'', include('pretalx.agenda.urls', namespace='agenda')),
    url(r'', include('pretalx.cfp.urls', namespace='cfp')),
]

if settings.DEBUG:
    with suppress(ImportError):
        import debug_toolbar
        urlpatterns += [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
