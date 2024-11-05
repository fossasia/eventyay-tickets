import base64
import logging
from datetime import datetime, timezone as tz
from decimal import Decimal

import pytz
import requests
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.db.models import Sum
from django_scopes import scopes_disabled
from django.db.models import Q

from ..base.models import BillingInvoice, Event, Order, Organizer
from ..base.models.organizer import OrganizerBillingModel
from ..base.services.mail import mail_send_task
from ..base.services.mail import CustomEmail, SendMailException, mail_send_task
from ..base.settings import GlobalSettingsObject
from ..control.stripe import process_auto_billing_charge_stripe
from ..helpers.jwt_generate import generate_sso_token
from .billing_invoice import generate_invoice_pdf

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


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retries up to 5 times with a 60-second delay
def monthly_billing_collect(self):
    """
    Collect billing on a monthly basis for all events
    schedule on 1st day of the month and collect billing for the previous month
    @param self: task instance
    """
    try:
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        logger.info(
            "Start - running task to collect billing on: %s", first_day_of_current_month
        )
        # Get the last month by subtracting one month from today
        last_month_date = (first_day_of_current_month - relativedelta(months=1)).date()
        gs = GlobalSettingsObject()
        ticket_rate = gs.settings.get("ticket_fee_percentage") or 2.5
        organizers = Organizer.objects.all()
        for organizer in organizers:
            events = Event.objects.filter(organizer=organizer)
            for event in events:
                try:
                    logger.info("Collecting billing data for event: %s", event.name)
                    billing_invoice = BillingInvoice.objects.filter(
                        event=event, monthly_bill=last_month_date, organizer=organizer
                    )
                    if billing_invoice:
                        logger.debug(
                            "Billing invoice already created for event: %s", event.name
                        )
                        continue
                    total_amount = calculate_total_amount_on_monthly(
                        event, last_month_date
                    )
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
                        updated_by=settings.PRETIX_EMAIL_NONE_VALUE,
                    )
                    billing_invoice.next_reminder_datetime = get_next_reminder_datetime(
                        settings.BILLING_REMINDER_SCHEDULE
                    )
                    billing_invoice.save()
                except Exception as e:
                    # If unexpected error happened, skip the event and continue to the next one
                    logger.error(
                        "Unexpected error happen when trying to collect billing for event: %s",
                        event.slug,
                    )
                    logger.error("Error: %s", e)
                    continue
        logger.info("End - completed task to collect billing on a monthly basis.")
    except DatabaseError as e:
        logger.error("Database error when trying to collect billing: %s", e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for billing collect.")
    except Exception as e:
        logger.error("Error happen when trying to collect billing: %s", e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for billing collect.")


@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Retries up to 5 times with a 60-second delay
def process_auto_billing_charge(self):
    """
    Process auto billing charge for all events
    schedule on 1st day of the month and collect billing for the previous month
    @param self: task instance
    """
    try:
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        logger.info("Start - running task to process auto billing charge on: %s", first_day_of_current_month)
        # Get the last month by subtracting one month from today
        last_month_date = (first_day_of_current_month - relativedelta(months=1)).date()
        billing_invoice = BillingInvoice.objects.filter(Q(monthly_bill=last_month_date) & Q(status='n'))
        for invoice in billing_invoice:
            try:
                logger.info("Processing auto billing charge for event: %s", invoice.event.name)

                # Get the organizer's billing settings
                billing_settings = OrganizerBillingModel.objects.filter(organizer_id=invoice.organizer_id).first()
                if not billing_settings or not billing_settings.stripe_customer_id:
                    logger.error("No billing settings or Stripe customer ID found for organizer %s",
                                 invoice.organizer.slug)
                    continue
                if not billing_settings.stripe_payment_method_id:
                    logger.error("No billing settings or Stripe payment method ID found for organizer %s",
                                 invoice.organizer.slug)
                    continue

                # Charge the organizer's payment method
                payment_intent = process_auto_billing_charge_stripe(billing_settings.organizer.slug, invoice.ticket_fee, currency=invoice.currency)
                # BillingInvoice.objects.filter(id=invoice.id).update(
                #     status='p',
                #     payment_intent_id=payment_intent.id,
                #     updated_at=today,
                # )

            except Exception as e:
                logger.error('Error happen when trying to process auto billing charge: %s', e)
                continue
    except Exception as e:
        logger.error('Error happen when trying to process auto billing charge: %s', e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for auto billing charge.")


def calculate_total_amount_on_monthly(event, last_month_date_start):
    """
    Calculate the total amount of all paid orders for the event in the previous month
    @param event: event to be calculated
    @param last_month_date_start: start date of month to be calculated
    @return: total amount of all paid orders for the event in the previous month
    """
    # Calculate the end date for last month
    last_month_date_end = (
        last_month_date_start + relativedelta(months=1, day=1)
    ) - relativedelta(days=1)

    # Use aggregate to sum the total of all paid orders within the date range
    total_amount = (
        event.orders.filter(
            status=Order.STATUS_PAID,
            datetime__range=[last_month_date_start, last_month_date_end],
        ).aggregate(total=Sum("total"))["total"]
        or 0
    )  # Return 0 if the result is None

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
    if not next_reminder:
        # Handle month wrapping (December to January)
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1
        # Select the first date in BILLING_REMIND_SCHEDULE for the next month
        next_reminder = datetime(next_year, next_month, reminder_schedule[0])

    return next_reminder


@shared_task(bind=True)
def billing_invoice_notification(self):
    """
    Send billing invoice notification to organizers
    @param self: task instance
    """
    logger.info("Start - running task to send billing invoice notification.")
    today = datetime.today()
    first_day_of_current_month = today.replace(day=1)
    billing_month = (first_day_of_current_month - relativedelta(months=1)).date()
    last_month_invoices = BillingInvoice.objects.filter(monthly_bill=billing_month)
    for invoice in last_month_invoices:
        if invoice.ticket_fee <= 0:
            # Do not send notification if ticket fee is 0
            continue
        # Get organizer's contact details
        organizer_billing = OrganizerBillingModel.objects.filter(
            organizer=invoice.organizer
        ).first()
        # Send email to organizer with invoice pdf
        mail_subject = f"Invoice #{invoice.id} for {invoice.event.name}"
        mail_content = f"Dear {organizer_billing.primary_contact_name},\n\nPlease find attached the invoice for your recent event."
        billing_invoice_send_email(
            mail_subject, mail_content, invoice, organizer_billing
        )
    logger.info("End - completed task to send billing invoice notification.")


@shared_task(bind=True)
def check_billing_status_for_warning(self):
    with scopes_disabled():
        pending_invoices = BillingInvoice.objects.filter(
            status=BillingInvoice.STATUS_PENDING, reminder_enabled=True
        )
        today = datetime.now(tz.utc)
        logger.info(
            "Start - running task to check billing status for warning on: %s", today
        )
        timezone = pytz.timezone(settings.TIME_ZONE)
        for invoice in pending_invoices:
            if invoice.ticket_fee <= 0:
                continue
            reminder_dates = invoice.reminder_schedule  # [15, 29]
            if not reminder_dates:
                continue
            reminder_dates.sort()
            for reminder_date in reminder_dates:
                reminder_date = datetime(today.year, today.month, reminder_date)
                reminder_date = timezone.localize(reminder_date)
                if (
                    not invoice.last_reminder_datetime
                    or invoice.last_reminder_datetime < reminder_date
                ) and reminder_date <= today:
                    # Send warning email to organizer
                    logger.info(
                        "Warning email is send to the organizer of %s",
                        invoice.event.slug,
                    )

                    # Get organizer's contact details
                    organizer_billing = OrganizerBillingModel.objects.filter(
                        organizer=invoice.organizer
                    ).first()

                    mail_subject = f"Warning: Invoice #{invoice.id} for {invoice.event.name} need to be paid"
                    mail_content = f"Dear {organizer_billing.primary_contact_name},\n\nPlease find attached the invoice for your recent event."
                    billing_invoice_send_email(
                        mail_subject, mail_content, invoice, organizer_billing
                    )

                    invoice.last_reminder_datetime = reminder_date
                    invoice.next_reminder_datetime = get_next_reminder_datetime(
                        invoice.reminder_schedule
                    )
                    invoice.save()
                    break
        logger.info("End - completed task to check billing status for warning.")


def billing_invoice_send_email(subject, content, invoice, organizer_billing):
    organizer_billing_contact = [organizer_billing.primary_contact_email]
    # generate invoice pdf
    pdf_buffer = generate_invoice_pdf(invoice, organizer_billing)
    # Send email to organizer
    pdf_content = pdf_buffer.getvalue()
    pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")
    mail_send_task.apply_async(
        kwargs={
            "subject": subject,
            "body": content,
            "sender": settings.PRETIX_EMAIL_NONE_VALUE,
            "to": organizer_billing_contact,
            "html": None,
            "attach_file_base64": pdf_base64,
            "attach_file_name": pdf_buffer.filename,
        }
    )
