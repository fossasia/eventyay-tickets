from django.urls import include, path
from eventyay.control.views import admin_views as views

urlpatterns = [
    # Authentication URLs
    path("auth/profile/", views.ProfileView.as_view(), name="auth.profile"),
    path("auth/signup", views.SignupView.as_view(), name="auth.signup"),
    path("auth/", include("django.contrib.auth.urls")),
    # User Management URLs
    path("users/", views.UserList.as_view(), name="user.list"),
    path("users/<uuid:pk>/", views.UserUpdate.as_view(), name="user.update"),
    # BBB Server Management URLs
    path("bbbs/", views.BBBServerList.as_view(), name="bbbserver.list"),
    path("bbbs/moveroom/", views.BBBMoveRoom.as_view(), name="bbbserver.moveroom"),
    path("bbbs/new/", views.BBBServerCreate.as_view(), name="bbbserver.create"),
    path("bbbs/<uuid:pk>/delete", views.BBBServerDelete.as_view(), name="bbbserver.delete"),
    path("bbbs/<uuid:pk>/", views.BBBServerUpdate.as_view(), name="bbbserver.update"),
    # Janus Server Management URLs
    path("janus/", views.JanusServerList.as_view(), name="janusserver.list"),
    path("janus/new/", views.JanusServerCreate.as_view(), name="janusserver.create"),
    path("janus/<uuid:pk>/delete", views.JanusServerDelete.as_view(), name="janusserver.delete"),
    path("janus/<uuid:pk>/", views.JanusServerUpdate.as_view(), name="janusserver.update"),
    # Turn Server Management URLs
    path("turns/", views.TurnServerList.as_view(), name="turnserver.list"),
    path("turns/new/", views.TurnServerCreate.as_view(), name="turnserver.create"),
    path("turns/<uuid:pk>/delete", views.TurnServerDelete.as_view(), name="turnserver.delete"),
    path("turnservers/<uuid:pk>/", views.TurnServerUpdate.as_view(), name="turnserver.update"),
    # Streaming Server Management URLs
    path("streamkey/", views.StreamkeyGenerator.as_view(), name="streamkey"),
    path("streamingservers/", views.StreamingServerList.as_view(), name="streamingserver.list"),
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
    # Feedback Management URLs
    path("feedback/", views.SystemLogList.as_view(), name="feedback.list"),
    path("feedback/<uuid:pk>/", views.SystemLogDetail.as_view(), name="feedback.detail"),
    # Conftool URLs
    path("conftool/syncposters/", views.ConftoolSyncPosters.as_view(), name="conftool.syncposters"),
    # Default index view
    path("", views.IndexView.as_view(), name="index"),
]
