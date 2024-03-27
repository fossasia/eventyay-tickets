import importlib

from django.apps import apps
from django.urls import include, path
from rest_framework import routers

from pretix.api.views import cart

from .views import (
    checkin, device, event, exporters, item, oauth, order, organizer, upload,
    user, version, voucher, waitinglist, webhooks,
)

router = routers.DefaultRouter()
router.register(r'organizers', organizer.OrganizerViewSet)

orga_router = routers.DefaultRouter()
orga_router.register(r'events', event.EventViewSet)
orga_router.register(r'subevents', event.SubEventViewSet)
orga_router.register(r'webhooks', webhooks.WebHookViewSet)
orga_router.register(r'seatingplans', organizer.SeatingPlanViewSet)
orga_router.register(r'giftcards', organizer.GiftCardViewSet)
orga_router.register(r'teams', organizer.TeamViewSet)
orga_router.register(r'devices', organizer.DeviceViewSet)
orga_router.register(r'exporters', exporters.OrganizerExportersViewSet, basename='exporters')

team_router = routers.DefaultRouter()
team_router.register(r'members', organizer.TeamMemberViewSet)
team_router.register(r'invites', organizer.TeamInviteViewSet)
team_router.register(r'tokens', organizer.TeamAPITokenViewSet)

event_router = routers.DefaultRouter()
event_router.register(r'subevents', event.SubEventViewSet)
event_router.register(r'clone', event.CloneEventViewSet)
event_router.register(r'items', item.ItemViewSet)
event_router.register(r'categories', item.ItemCategoryViewSet)
event_router.register(r'questions', item.QuestionViewSet)
event_router.register(r'quotas', item.QuotaViewSet)
event_router.register(r'vouchers', voucher.VoucherViewSet)
event_router.register(r'orders', order.OrderViewSet)
event_router.register(r'orderpositions', order.OrderPositionViewSet)
event_router.register(r'invoices', order.InvoiceViewSet)
event_router.register(r'revokedsecrets', order.RevokedSecretViewSet, basename='revokedsecrets')
event_router.register(r'taxrules', event.TaxRuleViewSet)
event_router.register(r'waitinglistentries', waitinglist.WaitingListViewSet)
event_router.register(r'checkinlists', checkin.CheckinListViewSet)
event_router.register(r'cartpositions', cart.CartPositionViewSet)
event_router.register(r'exporters', exporters.EventExportersViewSet, basename='exporters')

checkinlist_router = routers.DefaultRouter()
checkinlist_router.register(r'positions', checkin.CheckinListPositionViewSet, basename='checkinlistpos')

question_router = routers.DefaultRouter()
question_router.register(r'options', item.QuestionOptionViewSet)

item_router = routers.DefaultRouter()
item_router.register(r'variations', item.ItemVariationViewSet)
item_router.register(r'addons', item.ItemAddOnViewSet)
item_router.register(r'bundles', item.ItemBundleViewSet)

order_router = routers.DefaultRouter()
order_router.register(r'payments', order.PaymentViewSet)
order_router.register(r'refunds', order.RefundViewSet)

giftcard_router = routers.DefaultRouter()
giftcard_router.register(r'transactions', organizer.GiftCardTransactionViewSet)

# Force import of all plugins to give them a chance to register URLs with the router
for app in apps.get_app_configs():
    if hasattr(app, 'PretixPluginMeta'):
        if importlib.util.find_spec(app.name + '.urls'):
            importlib.import_module(app.name + '.urls')

urlpatterns = [
    path('', include(router.urls)),
    path('organizers/<str:organizer>/', include(orga_router.urls)),
    path('organizers/<str:organizer>/settings/', organizer.OrganizerSettingsView.as_view(),
        name="organizer.settings"),
    path('organizers/<str:organizer>/giftcards/<str:giftcard>/', include(giftcard_router.urls)),
    path('organizers/<str:organizer>/events/<str:event>/settings/', event.EventSettingsView.as_view(),
        name="event.settings"),
    path('organizers/<str:organizer>/events/<str:event>/', include(event_router.urls)),
    path('organizers/<str:organizer>/teams/<str:team>/', include(team_router.urls)),
    path('organizers/<str:organizer>/events/<str:event>/items/<str:item>/', include(item_router.urls)),
    path('organizers/<str:organizer>/events/<str:event>/questions/<str:question>/',
        include(question_router.urls)),
    path('organizers/<str:organizer>/events/<str:event>/checkinlists/<str:list>/',
        include(checkinlist_router.urls)),
    path('organizers/<str:organizer>/events/<str:event>/orders/<str:order>/', include(order_router.urls)),
    path("oauth/authorize", oauth.AuthorizationView.as_view(), name="authorize"),
    path("oauth/token", oauth.TokenView.as_view(), name="token"),
    path("oauth/revoke_token", oauth.RevokeTokenView.as_view(), name="revoke-token"),
    path("device/initialize", device.InitializeView.as_view(), name="device.initialize"),
    path("device/update", device.UpdateView.as_view(), name="device.update"),
    path("device/roll", device.RollKeyView.as_view(), name="device.roll"),
    path("device/revoke", device.RevokeKeyView.as_view(), name="device.revoke"),
    path("device/eventselection", device.EventSelectionView.as_view(), name="device.eventselection"),
    path("upload", upload.UploadView.as_view(), name="upload"),
    path("me", user.MeView.as_view(), name="user.me"),
    path("version", version.VersionView.as_view(), name="version"),
]
