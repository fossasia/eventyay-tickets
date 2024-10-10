import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import jwt
import requests
from django.conf import settings

from pretalx.celery_app import app

logger = logging.getLogger(__name__)


def generate_sso_token(user_email):
    jwt_payload = {
        "email": user_email,
        "has_perms": "orga.edit_schedule",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm="HS256")
    return jwt_token


def set_header_token(user_email):
    token = generate_sso_token(user_email)
    # Define the headers, including the Authorization header with the Bearer token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return headers


@app.task(
    bind=True,
    name="pretalx.orga.trigger_public_schedule",
    max_retries=3,
    default_retry_delay=60,
)
def trigger_public_schedule(
    self, is_show_schedule, event_slug, organiser_slug, user_email
):
    try:
        headers = set_header_token(user_email)
        payload = {"is_show_schedule": is_show_schedule}
        # Send the POST request with the payload and the headers
        ticket_uri = urljoin(
            settings.EVENTYAY_TICKET_BASE_PATH,
            f"api/v1/{organiser_slug}/{event_slug}/schedule-public/",
        )
        response = requests.post(ticket_uri, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        logger.error(
            "Error occurred when triggering hide/unhide schedule for tickets component."
            "Event: %s, Organiser: %s. Error: %s",
            event_slug, organiser_slug, e,
        )
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")
