from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from eventyay.eventyay_common.views import (
    account,
    auth,
    dashboards,
    event,
    organizer,
    team,
)
from eventyay.eventyay_common.views.orders import MyOrdersView
from eventyay.eventyay_common.views.sessions import MySessionsView

app_name = 'eventyay_common'

app_name = 'eventyay_common'


class DashboardView(TemplateView):
    template_name = 'pretixpresale/index.html'


urlpatterns = [
    path('logout/', auth.logout, name='auth.logout'),
    path('login/', auth.login, name='auth.login'),
    path('login/2fa/', auth.Login2FAView.as_view(), name='auth.login.2fa'),
    path('register/', auth.register, name='auth.register'),
    path('invite/<str:token>/', auth.invite, name='auth.invite'),
    path('forgot/', auth.Forgot.as_view(), name='auth.forgot'),
    path('forgot/recover/', auth.Recover.as_view(), name='auth.forgot.recover'),
    path('invite/<str:token>', auth.invite, name='auth.invite'),
    path('', dashboards.eventyay_common_dashboard, name='dashboard'),
    path('widgets.json/', dashboards.user_index_widgets_lazy, name='dashboard.widgets'),
    path('organizers/', organizer.OrganizerList.as_view(), name='organizers'),
    path('organizers/add', organizer.OrganizerCreate.as_view(), name='organizers.add'),
    path('organizer/<str:organizer>/', organizer.OrganizerUpdate.as_view(), name='organizer.update'),
    path('organizer/<str:organizer>/teams', team.TeamListView.as_view(), name='organizer.teams'),
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
                path('video-access/', event.VideoAccessAuthenticator.as_view(), name='event.create_access_to_video'),
            ]
        ),
    ),
    path('orders/', MyOrdersView.as_view(), name='orders'),
    path('sessions/', MySessionsView.as_view(), name='sessions'),
    path('account/', RedirectView.as_view(pattern_name='eventyay_common:account.general'), name='account'),
    path('account/general', account.GeneralSettingsView.as_view(), name='account.general'),
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
