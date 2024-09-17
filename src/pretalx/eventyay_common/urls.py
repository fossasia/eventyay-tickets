from django.urls import include, path

from pretalx.eventyay_common.views import auth

app_name = "eventyay_common"

urlpatterns = [
    path("oauth2/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("login/", auth.oauth2_login_view, name="oauth2_provider.login"),
    path("oauth2/callback/", auth.oauth2_callback, name="oauth2_callback"),
]
