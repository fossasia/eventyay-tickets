import logging
from datetime import datetime
from decimal import Decimal

import requests
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model

from ..base.models import BillingInvoice, Event, Order, Organizer
from ..base.settings import GlobalSettingsObject
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


@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Retries up to 5 times with a 60-second delay
def monthly_billing_collect(self):
    """
    Collect billing on a monthly basis for all events
    schedule on 1st day of the month and collect billing for the previous month
    @param self: task instance
    """
    try:
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        logger.info("Start - running task to collect billing on: %s", first_day_of_current_month)
        # Get the last month by subtracting one month from today
        last_month_date = (first_day_of_current_month - relativedelta(months=3)).date()
        gs = GlobalSettingsObject()
        ticket_rate = gs.settings.get('ticket_rate') or 2.5
        organizers = Organizer.objects.all()
        for organizer in organizers:
            events = Event.objects.filter(organizer=organizer)
            for event in events:
                try:
                    logger.info("Collecting billing for event: %s", event.name)
                    billing_invoice = BillingInvoice.objects.filter(event=event, monthly_bill=last_month_date,
                                                                    organizer=organizer)
                    if billing_invoice:
                        logger.debug("Billing invoice already created for event: %s", event.name)
                        continue
                    total_amount = calculate_total_amount_on_monthly(event, last_month_date)
                    tickets_fee = calculate_ticket_fee(total_amount, ticket_rate)
                    # Create a new billing invoice
                    billing_invoice = BillingInvoice(
                        organizer=organizer,
                        event=event,
                        amount=total_amount,
                        currency=event.currency,
                        ticket_fee=tickets_fee,
                        monthly_bill=last_month_date,
                        reminder_schedule=settings.BILLING_REMINDER_SCHEDULE,
                        created_at=today,
                        created_by=settings.PRETIX_EMAIL_NONE_VALUE,
                        updated_at=today,
                        updated_by=settings.PRETIX_EMAIL_NONE_VALUE
                    )
                    billing_invoice.next_reminder_datetime = get_next_reminder_datetime(
                        settings.BILLING_REMINDER_SCHEDULE)
                    billing_invoice.save()
                except Exception as e:
                    logger.error('Error happen when trying to collect billing for event: %s', event.slug)
                    logger.error('Error: %s', e)
                    continue
        logger.info("End - completed task to collect billing on a monthly basis.")
    except Exception as e:
        logger.error('Error happen when trying to collect billing: %s', e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for billing collect.")


def calculate_total_amount_on_monthly(event, last_month_date_start):
    """
    Calculate the total amount of all paid orders for the event in the previous month
    @param event: event to be calculated
    @param last_month_date_start: start date of month to be calculated
    @return: total amount of all paid orders for the event in the previous month
    """
    last_month_date_end = (last_month_date_start + relativedelta(months=1, day=1)) - relativedelta(days=1)
    orders = event.orders.filter(status=Order.STATUS_PAID, datetime__range=[last_month_date_start, last_month_date_end])
    total_amount = 0
    for order in orders:
        total_amount += order.total
    return total_amount


def calculate_ticket_fee(amount, rate):
    """
    Calculate the ticket fee based on the amount and rate
    @param amount: amount
    @param rate: rate in percentage
    @return: ticket fee
    """
    return amount * (Decimal(rate) / 100)


def get_next_reminder_datetime(reminder_schedule):
    """
    Get the next reminder datetime based on the reminder schedule
    @param reminder_schedule:
    @return:
    """
    reminder_schedule.sort()
    today = datetime.now()
    # Find the next scheduled day in the current month
    next_reminder = None
    for day in reminder_schedule:
        # Create a datetime object for each scheduled
        reminder_date = datetime(today.year, today.month, day)
        # Check if the scheduled day is in the future
        if reminder_date > today:
            next_reminder = reminder_date
            break
    return next_reminder
