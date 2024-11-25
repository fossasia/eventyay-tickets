import base64
import importlib.util
import logging
from datetime import datetime, timezone as tz
from decimal import Decimal
from importlib import import_module

import pytz
import requests
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db.models import Q
from django_scopes import scopes_disabled
from pretix_venueless.views import VenuelessSettingsForm

from pretix.helpers.stripe_utils import (
    confirm_payment_intent, process_auto_billing_charge_stripe,
)

from ..base.models import BillingInvoice, Event, Order, Organizer
from ..base.models.organizer import OrganizerBillingModel
from ..base.services.mail import mail_send_task
from ..base.settings import GlobalSettingsObject
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
            response = requests.post(
                "{}/api/v1/create-world/".format(settings.VIDEO_SERVER_HOSTNAME),
                json=payload,
                headers=headers,
            )
            setup_video_plugin(response.json())
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error: %s", str(e))
            self.retry(exc=e)
        except requests.exceptions.Timeout as e:
            logger.error("Request timed out: %s", str(e))
            self.retry(exc=e)
        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s", str(e))
            self.retry(exc=e)
        except ValueError as e:
            logger.error("Value error: %s", str(e))


def extract_jwt_config(world_data):
    """
    Extract the JWT configuration from the world data.
    @param world_data: A dictionary containing the world data.
    @return: A dictionary containing the JWT configuration.
    """
    config = world_data.get('config', {})
    jwt_secrets = config.get('JWT_secrets', [])
    jwt_config = jwt_secrets[0] if jwt_secrets else {}
    return {
        'secret': jwt_config.get('secret'),
        'issuer': jwt_config.get('issuer'),
        'audience': jwt_config.get('audience')
    }


def setup_video_plugin(world_data):
    """
     Setup the video plugin for the event.
     @param world_data: A dictionary containing the world data.
     if the plugin is installed, add the plugin to the event and save the video settings information.
     """
    jwt_config = extract_jwt_config(world_data)
    video_plugin = get_installed_plugin('pretix_venueless')
    event_id = world_data.get("id")
    if video_plugin:
        attach_plugin_to_event('pretix_venueless', event_id)
        video_settings = {
            'venueless_url': world_data.get('domain', ""),
            'venueless_secret': jwt_config.get('secret', ""),
            'venueless_issuer': jwt_config.get('issuer', ""),
            'venueless_audience': jwt_config.get('audience', ""),
            'venueless_all_items': True,
            'venueless_items': [],
            'venueless_questions': [],
        }
        save_video_settings_information(event_id, video_settings)
    else:
        logger.error("Video integration configuration failed - Plugin not installed")
        raise ValueError("Failed to configure video integration")


def save_video_settings_information(event_id, video_settings):
    """
    Save the video settings information to the event.
    @param event_id: A string representing the unique identifier for the event.
    @param video_settings:  A dictionary containing the video settings information.
    @return: The video configuration form.
    """
    try:
        with scopes_disabled():
            event_instance = Event.objects.get(slug=event_id)
            video_config_form = VenuelessSettingsForm(
                data=video_settings,
                obj=event_instance
            )
            if video_config_form.is_valid():
                video_config_form.save()
            else:
                logger.error("Video integration configuration failed - Validation errors: %s", video_config_form.errors)
                raise ValueError("Failed to validate video integration settings")
            return video_config_form
    except Event.DoesNotExist:
        logger.error("Event does not exist: %s", event_id)
        raise ValueError("Event does not exist")


def get_installed_plugin(plugin_name):
    """
    Check if a plugin is installed.
    @param plugin_name: A string representing the name of the plugin to check.
    @return: The installed plugin if it exists, otherwise None.
    """
    if importlib.util.find_spec(plugin_name) is not None:
        installed_plugin = import_module(plugin_name)
    else:
        installed_plugin = None
    return installed_plugin


def attach_plugin_to_event(plugin_name, event_slug):
    """
    Attach a plugin to an event.
    @param plugin_name: A string representing the name of the plugin to add.
    @param event_slug: A string representing the slug of the event to which the plugin should be added.
    @return: The event instance with the added plugin.
    """
    try:
        with scopes_disabled():
            event = Event.objects.get(slug=event_slug)
            event.plugins = add_plugin(event, plugin_name)
            event.save()
            return event
    except Event.DoesNotExist:
        logger.error("Event does not exist: %s", event_slug)
        raise ValueError("Event does not exist")


def add_plugin(event, plugin_name):
    """
    Add a plugin
    @param event: The event instance to which the plugin should be added.
    @param plugin_name: A string representing the name of the plugin to add.
    @return: The updated list of plugins for the event.
    """
    if not event.plugins:
        return plugin_name
    plugins = set(event.plugins.split(','))
    plugins.add(plugin_name)
    return ','.join(plugins)


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
@scopes_disabled()
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
                logger.info("Collecting billing data for event: %s", event.name)
                billing_invoice = BillingInvoice.objects.filter(
                    event=event, monthly_bill=last_month_date, organizer=organizer
                )
                if billing_invoice:
                    logger.info(
                        "Billing invoice already created for event: %s", event.name
                    )
                    continue
                # Continue if event order count on last month = 0
                if event.orders.filter(
                        status=Order.STATUS_PAID,
                        datetime__range=[
                            last_month_date,
                            (last_month_date + relativedelta(months=1, day=1)) - relativedelta(days=1),
                        ],
                ).count() == 0:
                    logger.info(
                        "No paid orders for event: %s in the last month", event.name
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
                logger.info("End - completed task to collect billing on a monthly basis.")
    except DatabaseError as e:
        logger.error("Database error when trying to collect billing: %s", e)
        # Retry the task if an exception occurs (with exponential backoff by default)
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for billing collect.")


@shared_task()
@scopes_disabled()
def update_billing_invoice_information(invoice_id: str):
    """
    Update billing invoice information after payment is succeeded
    @param invoice_id: A string representing the invoice ID
    """
    try:
        if not invoice_id:
            logger.error("Missing invoice_id in Stripe webhook metadata")
            return None
        invoice_information_updated = BillingInvoice.objects.filter(
            id=invoice_id,
        ).update(
            status=BillingInvoice.STATUS_PAID,
            paid_datetime=datetime.now(),
            payment_method='stripe',
            updated_at=datetime.now(),
            reminder_enabled=False
        )
        if not invoice_information_updated:
            logger.error("Invoice not found or already updated: %s", invoice_id)
            return None
        logger.info("Payment succeeded for invoice: %s", invoice_id)
    except BillingInvoice.DoesNotExist as e:
        logger.error("Invoice not found in database: %s", str(e))
        return None
    except DatabaseError as e:
        logger.error("Database error updating invoice: %s", str(e))
        return None


def retry_payment(payment_intent_id, organizer_id):
    """
    Retry a payment if the initial charge attempt failed.
    @param payment_intent_id: A string representing the payment intent ID
    @param organizer_id: A string representing the organizer's unique ID
    """
    try:
        with scopes_disabled():
            billing_settings = OrganizerBillingModel.objects.filter(
                organizer_id=organizer_id
            ).first()
            if not billing_settings or not billing_settings.stripe_payment_method_id:
                logger.error(
                    "No billing settings or Stripe payment method ID found for organizer %s", organizer_id
                )
                return
            confirm_payment_intent(payment_intent_id, billing_settings.stripe_payment_method_id)
            logger.info("Payment confirmed for payment intent: %s", payment_intent_id)
    except ValidationError as e:
        logger.error("Error retrying payment for %s: %s", payment_intent_id, str(e))


@shared_task()
@scopes_disabled()
def process_auto_billing_charge():
    """
    Process auto billing charge
    - If the ticket fee is greater than 0, the monthly bill is from the previous month, and the status is "pending" (n),
      the system will process the auto-billing charge for that invoice.
    - This task is scheduled to run on the 1st day of each month.
    """
    try:
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        last_month_date = (first_day_of_current_month - relativedelta(months=1)).date()
        pending_invoices = BillingInvoice.objects.filter(Q(monthly_bill=last_month_date) & Q(status='n'))
        for invoice in pending_invoices:
            if invoice.ticket_fee > 0:

                billing_settings = OrganizerBillingModel.objects.filter(organizer_id=invoice.organizer_id).first()
                if not billing_settings or not billing_settings.stripe_customer_id:
                    logger.error("No billing settings or Stripe customer ID found for organizer %s",
                                 invoice.organizer.slug)
                    continue
                if not billing_settings.stripe_payment_method_id:
                    logger.error("No billing settings or Stripe payment method ID found for organizer %s",
                                 invoice.organizer.slug)
                    continue

                metadata = {
                    'event_id': invoice.event_id,
                    'invoice_id': invoice.id,
                    'monthly_bill': invoice.monthly_bill,
                    'organizer_id': invoice.organizer_id,
                }
                process_auto_billing_charge_stripe(billing_settings.organizer.slug,
                                                   invoice.ticket_fee, currency=invoice.currency,
                                                   metadata=metadata, invoice_id=invoice.id)
            else:
                logger.info("No ticket fee for event: %s", invoice.event.slug)
                continue
    except ValidationError as e:
        logger.error('Error happen when trying to process auto billing charge: %s', e)


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
    total_amount = sum(
        order.net_total for order in event.orders.filter(
            status=Order.STATUS_PAID,
            datetime__range=[last_month_date_start, last_month_date_end],
        )
    ) or 0  # Return 0 if the result is None

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
@scopes_disabled()
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
        # Get organizer's contact details
        organizer_billing = OrganizerBillingModel.objects.filter(
            organizer=invoice.organizer
        ).first()
        if not organizer_billing:
            logger.error("No billing settings found for organizer %s", invoice.organizer.name)
            continue
        month_name = invoice.monthly_bill.strftime("%B")
        # Send email to organizer with invoice pdf
        mail_subject = f"{month_name} invoice for {invoice.event.name}"
        mail_content = (f"Dear {organizer_billing.primary_contact_name},\n\n"
                        f"Thank you for using our services! "
                        f"Please find attached for a summary of your invoice for {month_name}.\n\n"
                        f"Best regards,\n"
                        f"EventYay Team")

        billing_invoice_send_email(
            mail_subject, mail_content, invoice, organizer_billing
        )
    logger.info("End - completed task to send billing invoice notification.")


@shared_task(bind=True)
@scopes_disabled()
def retry_failed_payment(self):
    pending_invoices = BillingInvoice.objects.filter(
        status=BillingInvoice.STATUS_PENDING
    )
    today = datetime.now(tz.utc)
    logger.info(
        "Start - running task to retry failed payment: %s", today
    )
    timezone = pytz.timezone(settings.TIME_ZONE)
    for invoice in pending_invoices:
        if invoice.ticket_fee <= 0:
            continue
        reminder_dates = invoice.reminder_schedule
        if not reminder_dates or not invoice.stripe_payment_intent_id:
            continue
        reminder_dates.sort()
        for reminder_date in reminder_dates:
            reminder_date = datetime(today.year, today.month, reminder_date)
            reminder_date = timezone.localize(reminder_date)
            if (
                    not invoice.last_reminder_datetime
                    or invoice.last_reminder_datetime < reminder_date
            ) and reminder_date <= today:
                retry_payment(payment_intent_id=invoice.stripe_payment_intent_id, organizer_id=invoice.organizer_id)
                logger.info("Payment is retried for event %s", invoice.event.name)

                break
    logger.info("End - completed task to retry failed payment.")


@shared_task(bind=True)
@scopes_disabled()
def check_billing_status_for_warning(self):
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
        # marked invoice as expired if the due date is passed
        if today > (invoice.created_at + relativedelta(months=1)):
            logger.info("Invoice is expired for event %s", invoice.event.name)
            invoice.status = BillingInvoice.STATUS_EXPIRED
            invoice.reminder_enabled = False
            invoice.save()
            # move event's status to non-public
            invoice.event.live = False
            invoice.event.save()
            continue
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
                if not organizer_billing:
                    logger.error(
                        "No billing settings found for organizer %s",
                        invoice.organizer.name,
                    )
                    break
                month_name = invoice.monthly_bill.strftime("%B")

                mail_subject = f"Warning: {month_name} invoice for {invoice.event.name} need to be paid"
                mail_content = (
                    f"Dear {organizer_billing.primary_contact_name},\n\n"
                    f"This is a gentle reminder that your invoice for {month_name} is still pending "
                    f"and is due for payment soon. We value your prompt attention to this matter "
                    f"to ensure continued service without interruption.\n\n"
                    f"Invoice Details:\n"
                    f"- Invoice Date: {invoice.monthly_bill + relativedelta(months=1)}\n"
                    f"- Due Date: {invoice.created_at + relativedelta(months=1)} \n"
                    f"- Total Amount Due: {invoice.ticket_fee} {invoice.currency}\n\n"
                    f"If you have already made the payment, please disregard this notice. "
                    f"However, if you need additional time or have any questions, "
                    f"feel free to reach out to us at {settings.PRETIX_EMAIL_NONE_VALUE}.\n\n"
                    f"Thank you for your attention and for choosing us!\n\n"
                    f"Warm regards,\n"
                    f"EventYay Team"
                )
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
