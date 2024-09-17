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
    path("login/", auth.oauth2_login_view, name="oauth2_provider.login"),
    path("oauth2/callback/", auth.oauth2_callback, name="oauth2_callback"),
    path("webhook/organiser/", organiser_webhook, name="webhook.organiser"),
    path("webhook/team/", team_webhook, name="webhook.team"),
    path("webhook/event/", event_webhook, name="webhook.event"),
]
