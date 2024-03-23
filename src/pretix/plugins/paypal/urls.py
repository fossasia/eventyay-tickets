from django.urls import include, path, re_path

from pretix.multidomain import event_url

from .views import (
    abort, oauth_disconnect, oauth_return, redirect_view, success, webhook,
)

event_patterns = [
    path('paypal/', include([
        path('abort/', abort, name='abort'),
        path('return/', success, name='return'),
        path('redirect/', redirect_view, name='redirect'),

        re_path(r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/abort/', abort, name='abort'),
        re_path(r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/return/', success, name='return'),

        event_url(r'^webhook/$', webhook, name='webhook', require_live=False),
    ])),
]


urlpatterns = [
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/paypal/disconnect/',
        oauth_disconnect, name='oauth.disconnect'),
    path('_paypal/webhook/', webhook, name='webhook'),
    path('_paypal/oauth_return/', oauth_return, name='oauth.return'),
]
