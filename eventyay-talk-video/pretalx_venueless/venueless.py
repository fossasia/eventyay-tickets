from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils.timezone import now


def push_to_venueless(event):
    url = urljoin(event.settings.venueless_url, "schedule_update")
    token = event.settings.venueless_token
    response = requests.post(
        url,
        json={
            "domain": event.settings.custom_domain or settings.SITE_URL,
            "event": event.slug,
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    if response.status_code == 200:
        event.settings.venueless_last_push = now()
    return response
