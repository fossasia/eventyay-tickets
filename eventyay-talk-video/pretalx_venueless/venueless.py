from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils.timezone import now


def push_to_venueless(event):
    url = urljoin(event.venueless_settings.url, "schedule_update")
    token = event.venueless_settings.token
    response = requests.post(
        url,
        json={
            "domain": event.custom_domain or settings.SITE_URL,
            "event": event.slug,
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    if response.status_code == 200:
        event.venueless_settings.last_push = now()
    return response
