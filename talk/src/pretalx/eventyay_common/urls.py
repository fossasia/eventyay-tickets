from django.urls import include, path

from pretalx.eventyay_common.views import auth
from pretalx.eventyay_common.webhooks import (
    event_webhook,
    organiser_webhook,
    team_webhook,
)

app_name = "eventyay_common"

urlpatterns = [
    path("oauth2/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("login/", auth.OAuth2LoginView.as_view(), name="oauth2_provider.login"),
    path("register/", auth.register, name="register.account"),
    path("oauth2/callback/", auth.oauth2_callback, name="oauth2_callback"),
    path("webhook/organiser/", organiser_webhook, name="webhook.organiser"),
    path("webhook/team/", team_webhook, name="webhook.team"),
    path("webhook/event/", event_webhook, name="webhook.event"),
]
