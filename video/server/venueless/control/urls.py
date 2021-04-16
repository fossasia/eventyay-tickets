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
    path("worlds/", views.WorldList.as_view(), name="world.list"),
    path("worlds/new/", views.WorldCreate.as_view(), name="world.create"),
    path("worlds/<slug:pk>/admin", views.WorldAdminToken.as_view(), name="world.admin"),
    path("worlds/<slug:pk>/clear", views.WorldClear.as_view(), name="world.clear"),
    path("worlds/<slug:pk>/", views.WorldUpdate.as_view(), name="world.update"),
    path("", views.IndexView.as_view(), name="index"),
]
