from django.urls import include, path

from eventyay.control.views import admin_views as views

urlpatterns = [
    path("auth/profile/", views.ProfileView.as_view(), name="auth.profile"),
    path("auth/signup", views.SignupView.as_view(), name="auth.signup"),
    path("auth/", include("django.contrib.auth.urls")),
    # This shortcut creates the following urls:
    # auth/login/ [name='login']
    # auth/logout/ [name='logout']
    # auth/password_change/ [name='password_change']
    # auth/password_change/done/ [name='password_change_done']
    # auth/password_reset/ [name='password_reset']
    # auth/password_reset/done/ [name='password_reset_done']
    # auth/reset/<uidb64>/<token>/ [name='password_reset_confirm']
    # auth/reset/done/ [name='password_reset_complete']
    path("users/", views.UserList.as_view(), name="user.list"),
    path("users/<int:pk>/", views.UserUpdate.as_view(), name="user.update"),
    path("bbbs/", views.BBBServerList.as_view(), name="bbbserver.list"),
    path(
        "bbbs/moveroom/",
        views.BBBMoveRoom.as_view(),
        name="bbbserver.moveroom",
    ),
    path("bbbs/new/", views.BBBServerCreate.as_view(), name="bbbserver.create"),
    path(
        "bbbs/<uuid:pk>/delete",
        views.BBBServerDelete.as_view(),
        name="bbbserver.delete",
    ),
    path(
        "bbbs/<uuid:pk>/",
        views.BBBServerUpdate.as_view(),
        name="bbbserver.update",
    ),
    path("janus/", views.JanusServerList.as_view(), name="janusserver.list"),
    path(
        "janus/new/",
        views.JanusServerCreate.as_view(),
        name="janusserver.create",
    ),
    path(
        "janus/<uuid:pk>/delete",
        views.JanusServerDelete.as_view(),
        name="janusserver.delete",
    ),
    path(
        "janus/<uuid:pk>/",
        views.JanusServerUpdate.as_view(),
        name="janusserver.update",
    ),
    path("turns/", views.TurnServerList.as_view(), name="turnserver.list"),
    path(
        "turns/new/",
        views.TurnServerCreate.as_view(),
        name="turnserver.create",
    ),
    path(
        "turns/<uuid:pk>/delete",
        views.TurnServerDelete.as_view(),
        name="turnserver.delete",
    ),
    path(
        "turnservers/<uuid:pk>/",
        views.TurnServerUpdate.as_view(),
        name="turnserver.update",
    ),
    path("streamkey/", views.StreamkeyGenerator.as_view(), name="streamkey"),
    path(
        "streamingservers/",
        views.StreamingServerList.as_view(),
        name="streamingserver.list",
    ),
    path(
        "streamingservers/new/",
        views.StreamingServerCreate.as_view(),
        name="streamingserver.create",
    ),
    path(
        "streamingservers/<uuid:pk>/delete",
        views.StreamingServerDelete.as_view(),
        name="streamingserver.delete",
    ),
    path(
        "streamingservers/<uuid:pk>/",
        views.StreamingServerUpdate.as_view(),
        name="streamingserver.update",
    ),
    path("events/", views.EventList.as_view(), name="event.list"),
    path("events/new/", views.EventCreate.as_view(), name="event.create"),
    path("events/calendar", views.EventCalendar.as_view(), name="event.calendar"),
    path(
        "events/<slug:pk>/admin",
        views.EventAdminToken.as_view(),
        name="event.admin",
    ),
    path(
        "events/<slug:pk>/clear",
        views.EventClear.as_view(),
        name="event.clear",
    ),
    path("events/<slug:pk>/", views.EventUpdate.as_view(), name="event.update"),
    path("feedback/", views.FeedbackList.as_view(), name="feedback.list"),
    path(
        "feedback/<uuid:pk>/",
        views.FeedbackDetail.as_view(),
        name="feedback.detail",
    ),
    path(
        "conftool/syncposters/",
        views.ConftoolSyncPosters.as_view(),
        name="conftool.syncposters",
    ),
    path("", views.IndexView.as_view(), name="index"),
]
