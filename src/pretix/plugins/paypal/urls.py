from django.urls import include
from django.urls import re_path as url

from .views import (
    abort, isu_disconnect, isu_return, redirect_view, success, webhook, XHRView, PayView
)

event_patterns = [
    url(r'^paypal/', include([
        url(r'^abort/$', abort, name='abort'),
        url(r'^return/$', success, name='return'),
        url(r'^redirect/$', redirect_view, name='redirect'),
        url(r'^xhr/$', XHRView.as_view(), name='xhr'),
        url(r'^pay/(?P<order>[^/]+)/(?P<hash>[^/]+)/(?P<payment>[^/]+)/$', PayView.as_view(), name='pay'),
        url(r'^(?P<order>[^/][^w]+)/(?P<secret>[A-Za-z0-9]+)/xhr/$', XHRView.as_view(), name='xhr'),

        url(r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/abort/', abort, name='abort'),
        url(r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/return/', success, name='return'),
        url(r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/xhr/', XHRView.as_view(), name='xhr'),
    ])),
]

urlpatterns = [
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/paypal/disconnect/', isu_disconnect,
        name='isu.disconnect'),
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/paypal/return/$', isu_return, name='isu.return'),
    url(r'^_paypal/webhook/$', webhook, name='webhook')
]
