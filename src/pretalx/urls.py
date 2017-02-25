from django.conf import settings
from django.conf.urls import include, url

from .orga.urls import orga_urls

urlpatterns = [
    # url(r'^(?P<event>\w+)/schedule/export/', include('')),
    # url(r'^(?P<event>\w+)/schedule/', include('')),
    # url(r'^(?P<event>\w+)/cfp/', include('')),

    # url(r'^(?P<event>\w+)/submissions/availability/', include('')),
    # url(r'^(?P<event>\w+)/submissions/create/', include('')),
    # url(r'^(?P<event>\w+)/submissions/(?P<id>[0-9]+)/confirm/', include('')),
    # url(r'^(?P<event>\w+)/submissions/(?P<id>[0-9]+)/cancel/', include('')),
    # url(r'^(?P<event>\w+)/submissions/(?P<id>[0-9]+)/edit/', include('')),
    # url(r'^(?P<event>\w+)/submissions/(?P<id>[0-9]+)/', include('')),
    # url(r'^(?P<event>\w+)/submissions/', include('')),

    # url(r'^(?P<event>\w+)/people/', include('')),

    # url(r'^orga/(?P<event>\w+)/team/add/', include('')),
    # url(r'^orga/(?P<event>\w+)/team/', include('')),
    # url(r'^orga/(?P<event>\w+)/settings/', include('')),
    # url(r'^orga/(?P<event>\w+)/', include('')),

    url(r'^orga/', include(orga_urls, namespace='orga')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
