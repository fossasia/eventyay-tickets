from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from eventyay.control.views import gmail_oauth
from eventyay.control.views import organizer as organizer_control
from eventyay.control.views import organizer_views
from eventyay.eventyay_common.views import (
    account,
    auth,
    dashboards,
    event,
    event_api,
    organizer,
    team,
)
from eventyay.eventyay_common.views.account.email import EmailAddressManagementView
from eventyay.eventyay_common.views.orders import MyOrdersView
from eventyay.eventyay_common.views.sessions import MySessionsView


app_name = 'eventyay_common'


class DashboardView(TemplateView):
    template_name = 'pretixpresale/index.html'


urlpatterns = [
    path('logout/', auth.logout, name='auth.logout'),
    path(
        'login/',
        RedirectView.as_view(pattern_name='auth.login', permanent=True, query_string=True),
        name='auth.login.legacy',
    ),
    path(
        'login/2fa/',
        RedirectView.as_view(pattern_name='auth.login.2fa', permanent=True, query_string=True),
        name='auth.login.2fa.legacy',
    ),
    path('invite/<str:token>/', auth.invite, name='auth.invite'),
    path('forgot/', auth.Forgot.as_view(), name='auth.forgot'),
    path('forgot/recover/', auth.Recover.as_view(), name='auth.forgot.recover'),
    path('invite/<str:token>', auth.invite, name='auth.invite'),
    path('', dashboards.eventyay_common_dashboard, name='dashboard'),
    path('widgets.json/', dashboards.user_index_widgets_lazy, name='dashboard.widgets'),
    path('organizers/', organizer.OrganizerList.as_view(), name='organizers'),
    path('organizers/add', organizer.OrganizerCreate.as_view(), name='organizers.add'),
    path(
        'organizer/<str:organizer>/',
        organizer_views.organizer_view.OrganizerDashboard.as_view(),
        name='organizer.dashboard',
    ),
    path(
        'organizer/<str:organizer>/edit',
        organizer_views.organizer_view.OrganizerUpdate.as_view(),
        name='organizer.edit',
    ),
    path(
        'organizer/<str:organizer>/delete',
        organizer_views.organizer_view.OrganizerDelete.as_view(),
        name='organizer.delete',
    ),
    path(
        'organizer/<str:organizer>/events',
        organizer_views.organizer_view.OrganizerDetail.as_view(),
        name='organizer.events',
    ),
    path(
        'organizer/<str:organizer>/billing',
        organizer_views.organizer_view.BillingSettings.as_view(),
        name='organizer.billing',
    ),
    path('organizer/<str:organizer>/teams', organizer.OrganizerTeamsView.as_view(), name='organizer.teams'),
    path(
        'organizer/<str:organizer>/devices',
        organizer_views.device_view.DeviceListView.as_view(),
        name='organizer.devices',
    ),
    path(
        'organizer/<str:organizer>/device/add',
        organizer_views.device_view.DeviceCreateView.as_view(),
        name='organizer.devices.add',
    ),
    path(
        'organizer/<str:organizer>/device/<str:device>/edit',
        organizer_views.device_view.DeviceUpdateView.as_view(),
        name='organizer.devices.edit',
    ),
    path(
        'organizer/<str:organizer>/device/<str:device>/revoke',
        organizer_views.device_view.DeviceRevokeView.as_view(),
        name='organizer.devices.revoke',
    ),
    path(
        'organizer/<str:organizer>/devices/revoke-all',
        organizer_views.device_view.DeviceRevokeAllView.as_view(),
        name='organizer.devices.revoke-all',
    ),
    path(
        'organizer/<str:organizer>/device/<str:device>/logs',
        organizer_views.device_view.DeviceLogView.as_view(),
        name='organizer.devices.logs',
    ),
    path(
        'organizer/<str:organizer>/device/<str:device>/connect',
        organizer_views.device_view.DeviceConnectView.as_view(),
        name='organizer.devices.connect',
    ),
    path(
        'organizer/<str:organizer>/device/<str:device>/regenerate',
        organizer_views.device_view.DeviceRegenerateView.as_view(),
        name='organizer.devices.regenerate',
    ),
    path('organizer/<str:organizer>/gates', organizer_views.gate_view.GateListView.as_view(), name='organizer.gates'),
    path(
        'organizer/<str:organizer>/gate/add',
        organizer_views.gate_view.GateCreateView.as_view(),
        name='organizer.gates.add',
    ),
    path(
        'organizer/<str:organizer>/gate/<str:gate>/edit',
        organizer_views.gate_view.GateUpdateView.as_view(),
        name='organizer.gates.edit',
    ),
    path(
        'organizer/<str:organizer>/gate/<str:gate>/delete',
        organizer_views.gate_view.GateDeleteView.as_view(),
        name='organizer.gates.delete',
    ),
    path('organizer/<str:organizer>/export', organizer_control.ExportView.as_view(), name='organizer.export'),
    path('organizer/<str:organizer>/export/do', organizer_control.ExportDoView.as_view(), name='organizer.export.do'),
    path('organizer/<str:organizer>/team/add', team.TeamCreateView.as_view(), name='organizer.team.add'),
    path('organizer/<str:organizer>/team/<str:team>', team.TeamMemberView.as_view(), name='organizer.team'),
    path('organizer/<str:organizer>/team/<str:team>/edit', team.TeamUpdateView.as_view(), name='organizer.team.edit'),
    path(
        'organizer/<str:organizer>/team/<str:team>/delete', team.TeamDeleteView.as_view(), name='organizer.team.delete'
    ),
    path('events/', event.EventList.as_view(), name='events'),
    path('events/search/', event.EventSearchView.as_view(), name='events.search'),
    path('events/add', event.EventCreateView.as_view(), name='events.add'),
    path(
        'event/<str:organizer>/<str:event>/',
        include(
            [
                path('', dashboards.EventIndexView.as_view(), name='event.index'),
                path('widgets.json', dashboards.event_index_widgets_lazy, name='event.index.widgets'),
                path('settings/', event.EventUpdate.as_view(), name='event.update'),
                path(
                    'settings/gmail/connect/',
                    gmail_oauth.EventGmailOAuthConnectView.as_view(),
                    name='event.gmail.connect',
                ),
                path(
                    'settings/gmail/callback/',
                    gmail_oauth.EventGmailOAuthCallbackView.as_view(),
                    name='event.gmail.callback',
                ),
                path(
                    'settings/gmail/disconnect/',
                    gmail_oauth.EventGmailOAuthDisconnectView.as_view(),
                    name='event.gmail.disconnect',
                ),
                path('plugins/', event.EventPlugins.as_view(), name='event.plugins'),
                path('live/', event.EventLive.as_view(), name='event.live'),
                path('api/', event_api.EventAPIView.as_view(), name='event.api'),
                path('settings/clone/', event.EventCloneView.as_view(), name='event.clone'),
                path('video-access/', event.VideoAccessAuthenticator.as_view(), name='event.create_access_to_video'),
            ]
        ),
    ),
    path('orders/', MyOrdersView.as_view(), name='orders'),
    path('sessions/', MySessionsView.as_view(), name='sessions'),
    path('account/', RedirectView.as_view(pattern_name='eventyay_common:account.general'), name='account'),
    path('account/general', account.GeneralSettingsView.as_view(), name='account.general'),
    path('account/email', EmailAddressManagementView.as_view(), name='account.email'),
    path('account/notifications', account.NotificationSettingsView.as_view(), name='account.notifications'),
    path(
        'account/notification/off/<int:id>/<str:token>',
        account.NotificationFlipOffView.as_view(),
        name='account.notification.flip-off',
    ),
    path('account/2fa/', account.TwoFactorAuthSettingsView.as_view(), name='account.2fa'),
    path('account/2fa/enable', account.TwoFactorAuthEnableView.as_view(), name='account.2fa.enable'),
    path('account/2fa/disable', account.TwoFactorAuthDisableView.as_view(), name='account.2fa.disable'),
    path('account/2fa/add-device', account.TwoFactorAuthDeviceAddView.as_view(), name='account.2fa.add-device'),
    path(
        'account/2fa/totp/<str:device_id>/confirm',
        account.TwoFactorAuthDeviceConfirmTOTPView.as_view(),
        name='account.2fa.confirm.totp',
    ),
    path(
        'account/2fa/webauthn/<str:device_id>/confirm',
        account.TwoFactorAuthDeviceConfirmWebAuthnView.as_view(),
        name='account.2fa.confirm.webauthn',
    ),
    path(
        'account/2fa/<str:devicetype>/<str:device_id>/delete',
        account.TwoFactorAuthDeviceDeleteView.as_view(),
        name='account.2fa.delete',
    ),
    path(
        'account/2fa/regenemergency',
        account.TwoFactorAuthRegenerateEmergencyView.as_view(),
        name='account.2fa.regenemergency',
    ),
    path('account/locale', account.LanguageSwitchView.as_view(), name='account.locale'),
    path(
        'account/oauth/authorized-apps',
        account.OAuthAuthorizedAppListView.as_view(),
        name='account.oauth.authorized-apps',
    ),
    path(
        'account/oauth/authorized-app/<int:pk>/revoke',
        account.OAuthAuthorizedAppRevokeView.as_view(),
        name='account.oauth.authorized-app.revoke',
    ),
    path('account/oauth/own-apps', account.OAuthOwnAppListView.as_view(), name='account.oauth.own-apps'),
    path(
        'account/oauth/own-app/register',
        account.OAuthApplicationRegistrationView.as_view(),
        name='account.oauth.own-app.register',
    ),
    path('account/oauth/own-app/<int:pk>', account.OAuthApplicationUpdateView.as_view(), name='account.oauth.own-app'),
    path(
        'account/oauth/own-app/<int:pk>/roll',
        account.OAuthApplicationRollView.as_view(),
        name='account.oauth.own-app.roll',
    ),
    path(
        'account/oauth/own-app/<int:pk>/disable',
        account.OAuthApplicationDeleteView.as_view(),
        name='account.oauth.own-app.disable',
    ),
    path('account/history', account.HistoryView.as_view(), name='account.history'),
]
