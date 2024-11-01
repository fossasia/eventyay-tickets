import logging

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from ..helpers.jwt_generate import generate_sso_token

logger = logging.getLogger(__name__)


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retries up to 5 times with a 60-second delay
def send_organizer_webhook(self, user_id, organizer):
    # Define the payload to send to the webhook
    payload = {
        "name": organizer.get("name"),
        "slug": organizer.get("slug"),
        "action": organizer.get("action"),
    }
    # Define the headers, including the Authorization header with the Bearer token
    headers = get_header_token(user_id)

    try:
        # Send the POST request with the payload and the headers
        response = requests.post(
            settings.TALK_HOSTNAME + "/webhook/organiser/",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        # Log any errors that occur
        logger.error("Error sending webhook to talk component: %s", e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retries up to 5 times with a 60-second delay
def send_team_webhook(self, user_id, team):
    # Define the payload to send to the webhook
    payload = {
        "organiser_slug": team.get("organiser_slug"),
        "name": team.get("name"),
        "old_name": team.get("old_name"),
        "all_events": team.get("all_events"),
        "can_create_events": team.get("can_create_events"),
        "can_change_teams": team.get("can_change_teams"),
        "can_change_organiser_settings": team.get("can_change_organizer_settings"),
        "can_change_event_settings": team.get("can_change_event_settings"),
        "action": team.get("action"),
    }
    headers = get_header_token(user_id)

    try:
        # Send the POST request with the payload and the headers
        response = requests.post(
            settings.TALK_HOSTNAME + "/webhook/team/", json=payload, headers=headers
        )
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        # Log any errors that occur
        logger.error("Error sending webhook to talk component: %s", e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retries up to 5 times with a 60-second delay
def send_event_webhook(self, user_id, event, action):
    # Define the payload to send to the webhook
    user_model = get_user_model()
    user = user_model.objects.get(id=user_id)
    payload = {
        "organiser_slug": event.get("organiser_slug"),
        "name": event.get("name"),
        "slug": event.get("slug"),
        "date_from": event.get("date_from"),
        "date_to": event.get("date_to"),
        "timezone": event.get("timezone"),
        "locale": event.get("locale"),
        "locales": event.get("locales"),
        "user_email": user.email,
        "action": action,
    }
    headers = get_header_token(user_id)

    try:
        # Send the POST request with the payload and the headers
        response = requests.post(
            settings.TALK_HOSTNAME + "/webhook/event/", json=payload, headers=headers
        )
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        # Log any errors that occur
        logger.error("Error sending webhook to talk component: %s", e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retries up to 5 times with a 60-second delay
def create_world(self, is_video_creation, event_data):
    """
        Create a video system for the specified event.

        :param self: Task instance
        :param is_video_creation: A boolean indicating whether the user has chosen to add a video.
        :param event_data: A dictionary containing the following event details:
            - id (str): The unique identifier for the event.
            - title (str): The title of the event.
            - timezone (str): The timezone in which the event takes place.
            - locale (str): The locale for the event.
            - token (str): Authorization token for making the request.
            - has_permission (bool): Indicates if the user has 'can_create_events' permission or is in admin session mode.

        To successfully create a world, both conditions must be satisfied:
        - The user must have the necessary permission.
        - The user must choose to create a video.
    """
    event_slug = event_data.get("id")
    title = event_data.get("title")
    event_timezone = event_data.get("timezone")
    locale = event_data.get("locale")
    token = event_data.get("token")
    has_permission = event_data.get("has_permission")

    payload = {
        "id": event_slug,
        "title": title,
        "timezone": event_timezone,
        "locale": locale,
    }

    headers = {"Authorization": "Bearer " + token}

    if is_video_creation and has_permission:
        try:
            requests.post(
                "{}/api/v1/create-world/".format(settings.VIDEO_SERVER_HOSTNAME),
                json=payload,
                headers=headers,
            )
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error: %s", str(e))
            raise self.retry(exc=e)
        except requests.exceptions.Timeout as e:
            logger.error("Request timed out: %s", str(e))
            raise self.retry(exc=e)
        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s", str(e))
            raise self.retry(exc=e)


def get_header_token(user_id):
    # Fetch the user and organizer instances
    user_model = get_user_model()
    user = user_model.objects.get(id=user_id)
    # Generate the JWT token (assuming you have a function for that)
    token = generate_sso_token(user)

    # Define the headers, including the Authorization header with the Bearer token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return headers
