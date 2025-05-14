from django.urls import include, path
from django.views.generic import RedirectView

from pretix.eventyay_common.views import (
    account, dashboards, event, organizer, team,
)
from pretix.eventyay_common.views.orders import MyOrdersView

app_name = 'eventyay_common'

urlpatterns = [
    path('', dashboards.eventyay_common_dashboard, name='dashboard'),
    path('widgets.json/', dashboards.user_index_widgets_lazy, name='dashboard.widgets'),
    path('organizers/', organizer.OrganizerList.as_view(), name='organizers'),
    path('organizers/add', organizer.OrganizerCreate.as_view(), name='organizers.add'),
    path('organizer/<str:organizer>/update', organizer.OrganizerUpdate.as_view(), name='organizer.update'),
    path('organizer/<str:organizer>/teams', team.TeamListView.as_view(), name='organizer.teams'),
    path('organizer/<str:organizer>/team/add', team.TeamCreateView.as_view(), name='organizer.team.add'),
    path('organizer/<str:organizer>/team/<str:team>/edit', team.TeamUpdateView.as_view(), name='organizer.team.edit'),
    path('organizer/<str:organizer>/team/<str:team>/delete', team.TeamDeleteView.as_view(), name='organizer.team.delete'),
    path('events/', event.EventList.as_view(), name='events'),
    path('events/add', event.EventCreateView.as_view(), name='events.add'),
    path('event/<str:organizer>/<str:event>/', include([
        path('', dashboards.EventIndexView.as_view(), name='event.index'),
        path('widgets.json', dashboards.event_index_widgets_lazy, name='event.index.widgets'),
        path('settings/', event.EventUpdate.as_view(), name='event.update'),
        path('video-access/', event.VideoAccessAuthenticator.as_view(), name='event.create_access_to_video'),
    ])),
    path('orders/', MyOrdersView.as_view(), name='orders'),
    # TODO: We may move other /control/settings/xxx pages (which are for User settings) to under this "account" section as well.
    path('account/', RedirectView.as_view(pattern_name='eventyay_common:account.general'), name='account'),
    path('account/general/', account.GeneralSettingsView.as_view(), name='account.general'),
    path('account/notifications/', account.NotificationSettingsView.as_view(), name='account.notifications'),
    path('account/2fa/', account.TwoFactorAuthSettingsView.as_view(), name='account.2fa'),
    path('account/2fa/enable', account.TwoFactorAuthEnableView.as_view(), name='account.2fa.enable'),
    path('account/2fa/disable', account.TwoFactorAuthDisableView.as_view(), name='account.2fa.disable'),
    path('account/2fa/add-device', account.TwoFactorAuthDeviceAddView.as_view(), name='account.2fa.add-device'),
    path('account/2fa/<str:device_id>/confirm', account.TwoFactorAuthDeviceConfirmTOTPView.as_view(), name='account.2fa.confirm.totp'),
    path('account/oauth-list', account.DummyView.as_view(), name='account.oauth-list'),
    path('account/history', account.DummyView.as_view(), name='account.history'),
]
