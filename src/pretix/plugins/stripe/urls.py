from django.urls import include, path, re_path

from pretix.multidomain import event_url

from .views import (
    OrganizerSettingsFormView, ReturnView, ScaReturnView, ScaView,
    applepay_association, oauth_disconnect, oauth_return, redirect_view,
    webhook,
)

event_patterns = [
    path('stripe/', include([
        event_url(r'^webhook/$', webhook, name='webhook', require_live=False),
        path('redirect/', redirect_view, name='redirect'),
        path('return/<str:order>/<str:hash>/<int:payment>/', ReturnView.as_view(), name='return'),
        path('sca/<str:order>/<str:hash>/<int:payment>/', ScaView.as_view(), name='sca'),
        path('sca/<str:order>/<str:hash>/<int:payment>/return/',
            ScaReturnView.as_view(), name='sca.return'),
    ])),
    re_path(r'^.well-known/apple-developer-merchantid-domain-association$',
        applepay_association, name='applepay.association'),
]

organizer_patterns = [
    re_path(r'^.well-known/apple-developer-merchantid-domain-association$',
        applepay_association, name='applepay.association'),
]

urlpatterns = [
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/stripe/disconnect/',
        oauth_disconnect, name='oauth.disconnect'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/stripeconnect/',
        OrganizerSettingsFormView.as_view(), name='settings.connect'),
    path('_stripe/webhook/', webhook, name='webhook'),
    path('_stripe/oauth_return/', oauth_return, name='oauth.return'),
    re_path(r'^.well-known/apple-developer-merchantid-domain-association$',
        applepay_association, name='applepay.association'),
]
