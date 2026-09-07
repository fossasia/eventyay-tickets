from django.urls import include, path
from django.views.generic.base import RedirectView
from eventyay.control.views import admin_views as views


class SettingsTabRedirectView(RedirectView):
    pattern_name = "eventyay_admin:video_admin:settings"
    query_string = True
    tab = None

    def get_redirect_url(self, *args, **kwargs):
        url = super().get_redirect_url(*args, **kwargs)
        if self.tab:
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}tab={self.tab}"
        return url


urlpatterns = [
    # Authentication URLs
    path("auth/profile/", views.ProfileView.as_view(), name="auth.profile"),
    path("auth/signup", views.SignupView.as_view(), name="auth.signup"),
    path(
        "servers/<str:server_type>/<uuid:pk>/toggle-active/",
        views.VideoServerToggleActive.as_view(),
        name="server.toggle-active",
    ),
    # User Management URLs
    path("users/", views.UserList.as_view(), name="user.list"),
    path("users/<int:pk>/", views.UserUpdate.as_view(), name="user.update"),
    
    # Unified Video Settings
    path("settings/", views.VideoSettings.as_view(), name="settings"),
    
    # BBB Server Management URLs
    path("bbbs/", SettingsTabRedirectView.as_view(tab="bbb"), name="bbbserver.list"),
    path("bbbs/moveroom/", views.BBBMoveRoom.as_view(), name="bbbserver.moveroom"),
    path("bbbs/new/", views.BBBServerCreate.as_view(), name="bbbserver.create"),
    path("bbbs/<uuid:pk>/delete", views.BBBServerDelete.as_view(), name="bbbserver.delete"),
    path("bbbs/<uuid:pk>/", views.BBBServerUpdate.as_view(), name="bbbserver.update"),
    # Janus Server Management URLs
    path("janus/", SettingsTabRedirectView.as_view(tab="janus"), name="janusserver.list"),
    path("janus/new/", views.JanusServerCreate.as_view(), name="janusserver.create"),
    path("janus/<uuid:pk>/delete", views.JanusServerDelete.as_view(), name="janusserver.delete"),
    path("janus/<uuid:pk>/", views.JanusServerUpdate.as_view(), name="janusserver.update"),
    # Jitsi Server Management URLs
    path("jitsi/", SettingsTabRedirectView.as_view(tab="jitsi"), name="jitsiserver.list"),
    path("jitsi/new/", views.JitsiServerCreate.as_view(), name="jitsiserver.create"),
    path("jitsi/<uuid:pk>/delete", views.JitsiServerDelete.as_view(), name="jitsiserver.delete"),
    path("jitsi/<uuid:pk>/", views.JitsiServerUpdate.as_view(), name="jitsiserver.update"),
    # Turn Server Management URLs
    path("turns/", SettingsTabRedirectView.as_view(tab="turn"), name="turnserver.list"),
    path("turns/new/", views.TurnServerCreate.as_view(), name="turnserver.create"),
    path("turns/<uuid:pk>/delete", views.TurnServerDelete.as_view(), name="turnserver.delete"),
    path("turnservers/<uuid:pk>/", views.TurnServerUpdate.as_view(), name="turnserver.update"),
    # Streaming Server Management URLs
    path("streamingservers/", SettingsTabRedirectView.as_view(tab="streaming"), name="streamingserver.list"),
    path("streamingservers/new/", views.StreamingServerCreate.as_view(), name="streamingserver.create"),
    path("streamingservers/<uuid:pk>/delete", views.StreamingServerDelete.as_view(), name="streamingserver.delete"),
    path("streamingservers/<uuid:pk>/", views.StreamingServerUpdate.as_view(), name="streamingserver.update"),
    # Event Management URLs
    path("events/", views.EventList.as_view(), name="event.list"),
    path("events/new/", views.EventCreate.as_view(), name="event.create"),
    path("events/calendar", views.EventCalendar.as_view(), name="event.calendar"),
    path("events/<slug:pk>/admin", views.EventAdminToken.as_view(), name="event.admin"),
    path("events/<slug:pk>/clear", views.EventClear.as_view(), name="event.clear"),
    path("events/<slug:pk>/", views.EventUpdate.as_view(), name="event.update"),
    # SystemLog Management URLs
    path("systemlog/", views.SystemLogList.as_view(), name="systemlog.list"),
    path("systemlog/<uuid:pk>/", views.SystemLogDetail.as_view(), name="systemlog.detail"),
    # Default index view redirects to settings
    path("", RedirectView.as_view(pattern_name="eventyay_admin:video_admin:settings", query_string=True), name="index"),
]
