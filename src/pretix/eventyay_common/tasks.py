import logging
import requests

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from ..helpers.jwt_generate import generate_sso_token

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Retries up to 5 times with a 60-second delay
def send_organizer_webhook(self, user_id, organizer):
    # Define the payload to send to the webhook
    payload = {
        'name': organizer.get('name'),
        'slug': organizer.get('slug'),
        'action': organizer.get('action')
    }
    # Define the headers, including the Authorization header with the Bearer token
    headers = get_header_token(user_id)

    try:
        # Send the POST request with the payload and the headers
        response = requests.post(settings.TALK_HOSTNAME + '/webhook/organiser/',
                                 json=payload,
                                 headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        # Log any errors that occur
        logger.error('Error sending webhook to talk component: %s', e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")


@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Retries up to 5 times with a 60-second delay
def send_team_webhook(self, user_id, team):
    # Define the payload to send to the webhook
    payload = {
        'organiser_slug': team.get('organiser_slug'),
        'name': team.get('name'),
        'old_name': team.get('old_name'),
        'all_events': team.get('all_events'),
        'can_create_events': team.get('can_create_events'),
        'can_change_teams': team.get('can_change_teams'),
        'can_change_organiser_settings': team.get('can_change_organizer_settings'),
        'can_change_event_settings': team.get('can_change_event_settings'),
        'action': team.get('action')
    }
    headers = get_header_token(user_id)

    try:
        # Send the POST request with the payload and the headers
        response = requests.post(settings.TALK_HOSTNAME + '/webhook/team/',
                                 json=payload,
                                 headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        # Log any errors that occur
        logger.error('Error sending webhook to talk component: %s', e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")


@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Retries up to 5 times with a 60-second delay
def send_event_webhook(self, user_id, event, action):
    # Define the payload to send to the webhook
    user_model = get_user_model()
    user = user_model.objects.get(id=user_id)
    payload = {
        'organiser_slug': event.get('organiser_slug'),
        'name': event.get('name'),
        'slug': event.get('slug'),
        'is_public': event.get('is_public'),
        'date_from': event.get('date_from'),
        'date_to': event.get('date_to'),
        'timezone': event.get('timezone'),
        'locale': event.get('locale'),
        'locales': event.get('locales'),
        'user_email': user.email,
        'action': action
    }
    headers = get_header_token(user_id)

    try:
        # Send the POST request with the payload and the headers
        response = requests.post(settings.TALK_HOSTNAME + '/webhook/event/',
                                 json=payload,
                                 headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
    except requests.RequestException as e:
        # Log any errors that occur
        logger.error('Error sending webhook to talk component: %s', e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for sending organizer webhook.")


def get_header_token(user_id):
    # Fetch the user and organizer instances
    user_model = get_user_model()
    user = user_model.objects.get(id=user_id)
    # Generate the JWT token (assuming you have a function for that)
    token = generate_sso_token(user)

    # Define the headers, including the Authorization header with the Bearer token
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    return headers
