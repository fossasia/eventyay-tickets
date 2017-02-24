from django.conf import settings
from django.conf.urls import include, url

urlpatterns = []
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
