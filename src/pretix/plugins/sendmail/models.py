import ast
import bleach
import json
import logging

from django.db import models
from django.utils.timezone import now
from i18nfield.fields import I18nTextField

from pretix.base.email import get_email_context
from pretix.base.models import Event, InvoiceAddress, Order, OrderPosition, User
from pretix.base.i18n import LazyI18nString, language
from pretix.base.services.mail import TolerantDict, mail

logger = logging.getLogger(__name__)


class ComposingFor(models.TextChoices):
    ATTENDEES = 'attendees', 'Attendees'
    TEAMS = 'teams', 'Teams'


class QueuedMail(models.Model):
    """
    Stores queued emails composed by organizers for later sending.

    :param event: The event this queued mail is associated with.
    :type event: Event
    :param user: The user (organizer/admin) who queued this email.
    :type user: User
    :param to_users: A list of dictionaries storing metadata for each recipient,
                     including email, matching orders, positions, and items.
                     Format:
                     [
                         {
                             "email": "user@example.com",
                             "orders": ["123", "456"],
                             "positions": ["789"],
                             "items": ["1", "2"],
                             "sent": False,
                             "error": null,
                             "team": 10                   # Team id, the team member is present in.
                         },
                         ...
                     ]
    :type to_users: list[dict]

    :param composing_for: To whom the organizer is composing email for. Either "attendees" or "teams"
    :type raw_composing_for: str

    :param raw_subject: The untranslated subject, stored as an i18n-aware string.
                        (e.g., {"en": "Hello", "de": "Hallo"}).
    :type raw_subject: I18nTextField

    :param raw_message: The untranslated body of the email, also i18n-aware.
    :type raw_message: I18nTextField

    :param filters: A JSON structure capturing all user-selected filters from the MailForm
                    that define the target audience and selection logic.

                    Expected structure:
                    {
                        "recipients": "orders" | "attendees" | "both",
                        "sendto": ["p", "na", ...],              # Order status filters
                        "items": [1, 2, 3],                      # Selected item IDs
                        "checkin_lists": [4, 5],                 # Check-in list IDs
                        "filter_checkins": true | false,         # Enable check-in filtering
                        "not_checked_in": true | false,          # Only target not-checked-in users
                        "subevent": 10,                          # Single subevent ID
                        "subevents_from": "2025-07-01T00:00:00Z",# ISO-formatted datetime
                        "subevents_to": "2025-07-07T00:00:00Z",
                        "created_from": "2025-06-01T00:00:00Z",  # Order creation window
                        "created_to": "2025-06-30T00:00:00Z",
                        "orders": [101, 102, 103]                # Final matched order IDs (snapshot)
                        "teams": [1, 2, 3]                       # Teams primary keys, used to compose emails for Teams 
                    }
    :type filters: dict

    :param reply_to: Optional reply-to address to use in sent email.
    :type reply_to: str

    :param bcc: Comma-separated list of BCC recipients.
    :type bcc: str

    :param locale: Preferred default locale if not overridden per recipient.
    :type locale: str

    :param attachments: List of file UUIDs to be attached to the email.
    :type attachments: list[str]

    :param created: Timestamp of when the queued mail was created.
    :type created: datetime

    :param updated: Timestamp of the last update.
    :type updated: datetime

    :param sent_at: When the email was sent (fully completed).
    :type sent_at: datetime or None
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="queued_mails")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    to_users = models.JSONField(null=True, blank=True)
    composing_for = models.CharField(max_length=20, choices=ComposingFor.choices, default=ComposingFor.ATTENDEES)

    raw_subject = I18nTextField(null=True, blank=True)
    raw_message = I18nTextField(null=True, blank=True)

    filters = models.JSONField(null=True, blank=True)

    reply_to = models.CharField(max_length=100, null=True, blank=True)
    bcc = models.TextField(null=True, blank=True)  # comma-separated
    locale = models.CharField(max_length=16, null=True, blank=True)
    attachments = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"QueuedMail(event={self.event.slug}, subject={self.raw_subject[:30]}, sent_at={self.sent_at})"

    def clean(self):
        """
        Validates the structure of the filters and to_users fields, if present.
        Ensures only known keys are allowed in each.
        """
        # Validate to_users list
        from django.core.exceptions import ValidationError
        if self.to_users:
            allowed_user_keys = {
                'email', 'orders', 'positions', 'items', 'sent', 'error', 'filter_checkins', 'team'
            }

            for i, user_dict in enumerate(self.to_users):
                if extra_user_keys := set(user_dict.keys()) - allowed_user_keys:
                    raise ValidationError(f"Invalid to_user keys in entry {i}: {extra_user_keys}")

        # Validate filters dict
        if self.filters:
            allowed_filter_keys = {
                'recipients', 'sendto', 'orders', 'items', 'checkin_lists', 'filter_checkins',
                'not_checked_in', 'subevent', 'subevents_from', 'subevents_to',
                'created_from', 'created_to', 'teams'
            }
            extra_filter_keys = set(self.filters.keys()) - allowed_filter_keys
            if extra_filter_keys:
                raise ValidationError(f"Invalid filter keys: {extra_filter_keys}")

    def subject_localized(self, locale=None):
        """
        Returns localized subject if LazyI18nString.
        """
        subject = LazyI18nString(self.raw_subject)
        return subject.localize(locale or self.locale or self.event.settings.locale)

    def message_localized(self, locale=None):
        """
        Returns localized message if LazyI18nString.
        """
        message = LazyI18nString(self.raw_message)
        return message.localize(locale or self.locale or self.event.settings.locale)

    def send(self, async_send=True):
        """
        Sends queued email to each recipient in `to_users`.
        Uses their stored metadata and updates send status individually.
        """
        if self.sent_at:
            return  # Already sent
        if not self.to_users:
            return False  # Nothing to send

        subject = LazyI18nString(self.raw_subject)
        message = LazyI18nString(self.raw_message)
        changed = False

        for recipient in self.to_users:
            if recipient.get("sent"):
                continue  # Already sent
            result = self._send_to_recipient(recipient, subject, message)
            changed = changed or result

        self._finalize_send_status()
        return True

    def _build_email_context(self, order, position, position_or_address, recipient):
        try:
            if self.composing_for == ComposingFor.ATTENDEES:
                return get_email_context(
                    event=self.event,
                    order=order,
                    position=position,
                    position_or_address=position_or_address,
                )
            else:
                return get_email_context(event=self.event)
        except Exception as e:
            logger.exception("Error while generating email context")
            recipient["error"] = f"Context error: {str(e)}"
            return None

    def _finalize_send_status(self):
        if all(r.get("sent", False) for r in self.to_users):
            self.sent_at = now()
        else:
            self.sent_at = None
        self.save(update_fields=["to_users", "sent_at"])


    def _send_to_recipient(self, recipient, subject, message):
        from pretix.base.services.mail import SendMailException
        email = recipient.get("email")
        if not email:
            return False

        order_id = (orders := recipient.get("orders")) and orders[0]
        position_id = (positions := recipient.get("positions")) and positions[0]

        order = Order.objects.filter(pk=order_id, event=self.event).first() if order_id else None
        position = OrderPosition.objects.filter(pk=position_id).first() if position_id else None

        try:
            ia = order.invoice_address if order else None
        except InvoiceAddress.DoesNotExist:
            ia = InvoiceAddress(order=order) if order else None

        position_or_address = position or ia
        context = self._build_email_context(order, position, position_or_address, recipient)
        if context is None:
            return True  # Error already logged

        try:
            mail(
                email=email,
                subject=subject,
                template=message,
                context=context,
                event=self.event,
                locale=order.locale if order else self.locale,
                order=order,
                position=position,
                sender=self.event.settings.get('mail_from'),
                event_bcc=self.bcc,
                event_reply_to=self.reply_to,
                attach_cached_files=self.attachments,
                user=self.user,
                auto_email=False,
            )
            recipient["sent"] = True
            recipient["error"] = None
        except SendMailException as e:
            recipient["error"] = str(e)
            recipient["sent"] = False
        except Exception as e:
            recipient["error"] = f"Internal error: {str(e)}"
            recipient["sent"] = False
            logger.exception("Unexpected error while sending to %s: %s", email, str(e))

        return True

    def get_recipient_emails(self):
        """
        Resolve and return the full list of unique email addresses
        this queued mail will send to.
        """
        emails = set()
        filters = self.filters or {}
        recipients = filters.get("recipients", "orders")

        orders_qs = Order.objects.filter(
            pk__in=filters.get('orders', []),
            event=self.event
        ).prefetch_related('positions__addons')

        if recipients in ("both", "attendees"):
            for order in orders_qs:
                for pos in order.positions.all():
                    if pos.attendee_email:
                        emails.add(pos.attendee_email.strip().lower())

        if recipients in ("both", "orders"):
            for order in orders_qs:
                if order.email:
                    emails.add(order.email.strip().lower())

        return sorted(emails)

    def populate_to_users(self, save=True):
        """
        Resolves recipients and populates `to_users` with grouped metadata.
        """
        from collections import defaultdict

        filters = self.filters or {}
        recipients_mode = filters.get("recipients", "orders")
        orders_qs = Order.objects.filter(
            pk__in=filters.get('orders', []),
            event=self.event
        ).prefetch_related('positions__item', 'positions__addons')

        recipients = defaultdict(lambda: {
            "orders": set(),
            "positions": set(),
            "items": set()
        })

        if recipients_mode in ("both", "attendees"):
            for order in orders_qs:
                for pos in order.positions.all():
                    if pos.attendee_email:
                        email = pos.attendee_email.strip().lower()
                        recipients[email]["orders"].add(str(order.pk))
                        recipients[email]["positions"].add(str(pos.pk))
                        recipients[email]["items"].add(str(pos.item.pk))

        if recipients_mode in ("both", "orders"):
            for order in orders_qs:
                if order.email:
                    email = order.email.strip().lower()
                    recipients[email]["orders"].add(str(order.pk))
                    item_ids = order.positions.values_list('item__pk', flat=True)
                    recipients[email]["items"].update(str(iid) for iid in item_ids)

        # Convert sets to lists for JSON serializability
        self.to_users = [
            {
                "email": email,
                "orders": list(data["orders"]),
                "positions": list(data["positions"]),
                "items": list(data["items"]),
                "sent": False,
                "error": None,
            }
            for email, data in recipients.items()
        ]

        if save:
            self.save(update_fields=["to_users"])

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
