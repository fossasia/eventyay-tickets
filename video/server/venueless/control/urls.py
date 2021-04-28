from django.urls import include, path

from . import views

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
    path("bbbs/new/", views.BBBServerCreate.as_view(), name="bbbserver.create"),
    path(
        "bbbs/<uuid:pk>/delete",
        views.BBBServerDelete.as_view(),
        name="bbbserver.delete",
    ),
    path("bbbs/<uuid:pk>/", views.BBBServerUpdate.as_view(), name="bbbserver.update"),
    path("janus/", views.JanusServerList.as_view(), name="janusserver.list"),
    path("janus/new/", views.JanusServerCreate.as_view(), name="janusserver.create"),
    path(
        "janus/<uuid:pk>/delete",
        views.JanusServerDelete.as_view(),
        name="janusserver.delete",
    ),
    path(
        "janus/<uuid:pk>/", views.JanusServerUpdate.as_view(), name="janusserver.update"
    ),
    path("turns/", views.TurnServerList.as_view(), name="turnserver.list"),
    path("turns/new/", views.TurnServerCreate.as_view(), name="turnserver.create"),
    path(
        "turns/<uuid:pk>/delete",
        views.TurnServerDelete.as_view(),
        name="turnserver.delete",
    ),
    path(
        "turns/<uuid:pk>/", views.TurnServerUpdate.as_view(), name="turnserver.update"
    ),
    path("worlds/", views.WorldList.as_view(), name="world.list"),
    path("worlds/new/", views.WorldCreate.as_view(), name="world.create"),
    path("worlds/<slug:pk>/admin", views.WorldAdminToken.as_view(), name="world.admin"),
    path("worlds/<slug:pk>/clear", views.WorldClear.as_view(), name="world.clear"),
    path("worlds/<slug:pk>/", views.WorldUpdate.as_view(), name="world.update"),
    path("", views.IndexView.as_view(), name="index"),
]
