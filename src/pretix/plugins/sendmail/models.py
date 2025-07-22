import logging

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.timezone import now
from i18nfield.fields import I18nTextField

from pretix.base.email import get_email_context
from pretix.base.models import Event, InvoiceAddress, Order, OrderPosition, User
from pretix.base.i18n import LazyI18nString
from pretix.base.services.mail import mail


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

    :param composing_for: To whom the organizer is composing email for. Either "attendees" or "teams"
    :type raw_composing_for: str

    :param subject: The untranslated subject, stored as an i18n-aware string.
                        (e.g., {"en": "Hello", "de": "Hallo"}).
    :type subject: I18nTextField

    :param message: The untranslated body of the email, also i18n-aware.
    :type message: I18nTextField

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
    composing_for = models.CharField(max_length=20, choices=ComposingFor.choices, default=ComposingFor.ATTENDEES)

    subject = I18nTextField(null=True, blank=True)
    message = I18nTextField(null=True, blank=True)

    reply_to = models.CharField(max_length=100, null=True, blank=True)
    bcc = models.TextField(null=True, blank=True)  # comma-separated
    locale = models.CharField(max_length=16, null=True, blank=True)
    attachments = ArrayField(base_field=models.UUIDField(), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"QueuedMail(event={self.event.slug}, sent_at={self.sent_at})"

    def subject_localized(self, locale=None):
        """
        Returns localized subject if LazyI18nString.
        """
        subject = LazyI18nString(self.subject)
        return subject.localize(locale or self.locale or self.event.settings.locale)

    def message_localized(self, locale=None):
        """
        Returns localized message if LazyI18nString.
        """
        message = LazyI18nString(self.message)
        return message.localize(locale or self.locale or self.event.settings.locale)

    def send(self, async_send=True):
        """
        Sends queued email to each recipients.
        Uses their stored metadata and updates send status individually.
        """
        if self.sent_at:
            return  # Already sent
        recipients = self.recipients.all()
        if not recipients.exists():
            return False  # Nothing to send

        subject = LazyI18nString(self.subject)
        message = LazyI18nString(self.message)
        changed = False

        for recipient in recipients:
            if recipient.sent:
                continue
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
            recipient.error = f"Context error: {str(e)}"
            recipient.save(update_fields=["error"])
            return None

    def _finalize_send_status(self):
        if all(r.sent for r in self.recipients.all()):
            self.sent_at = now()
        else:
            self.sent_at = None
        self.save(update_fields=["sent_at"])

    def _send_to_recipient(self, recipient, subject, message):
        from pretix.base.services.mail import SendMailException
        email = recipient.email
        if not email:
            return False

        order_id = recipient.orders[0] if recipient.orders else None
        position_id = recipient.positions[0] if recipient.positions else None

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
            recipient.sent = True
            recipient.error = None
        except SendMailException as se:
            recipient.sent = False
            recipient.error = str(se)
            recipient.save(update_fields=["sent", "error"])
            logger.exception("SendMailException error while sending to %s: %s", email, str(e))
        except Exception as e:
            recipient.sent = False
            recipient.error = f"Internal error: {str(e)}"
            recipient.save(update_fields=["sent", "error"])
            logger.exception("Unexpected error while sending to %s", email)

        recipient.save(update_fields=["sent", "error"])
        return True

    def get_recipient_emails(self):
        """
        Resolve and return the full list of unique email addresses
        this queued mail will send to.
        """
        return sorted(set(r.email.strip().lower() for r in self.recipients.all() if r.email))
    
    def populate_to_users(self, save=True):
        """
        Resolves recipients and populates to_users with metadata.
        """
        from collections import defaultdict

        filters = getattr(self, 'filters_data', None)
        if not filters:
            return

        recipients_mode = filters.recipients or "orders"
        orders_qs = Order.objects.filter(
            pk__in=filters.orders,
            event=self.event
        ).prefetch_related('positions__item', 'positions__addons', 'positions__checkins')

        recipients = defaultdict(lambda: {
            "orders": set(),
            "positions": set(),
            "items": set()
        })

        for order in orders_qs:
            order_fallback_needed = False
            attendee_found = False

            for pos in order.positions.all():
                if pos.attendee_email:
                    attendee_found = True
                    email = pos.attendee_email.strip().lower()
                    recipients[email]["orders"].add(str(order.pk))
                    recipients[email]["positions"].add(str(pos.pk))
                    recipients[email]["items"].add(str(pos.item.pk))
                else:
                    # No attendee email; maybe fallback later
                    order_fallback_needed = True

            # Fallback to order email if needed
            if (
                order_fallback_needed and
                not attendee_found and
                recipients_mode == "attendees" and
                order.email
            ):
                email = order.email.strip().lower()
                recipients[email]["orders"].add(str(order.pk))
                item_ids = order.positions.values_list('item__pk', flat=True)
                recipients[email]["items"].update(str(iid) for iid in item_ids)

            # Explicit inclusion of orders
            if recipients_mode in ("both", "orders") and order.email:
                email = order.email.strip().lower()
                recipients[email]["orders"].add(str(order.pk))
                item_ids = order.positions.values_list('item__pk', flat=True)
                recipients[email]["items"].update(str(iid) for iid in item_ids)

        # Clear and insert fresh records
        self.recipients.all().delete()

        objs = [
            QueuedMailToUser(
                mail=self,
                email=email,
                orders=list(data["orders"]),
                positions=list(data["positions"]),
                items=list(data["items"]),
                sent=False,
                error=None,
            )
            for email, data in recipients.items()
        ]

        QueuedMailToUser.objects.bulk_create(objs)
        if save:
            self.save()


class QueuedMailToUser(models.Model):
    """
    Represents a single recipient of a QueuedMail.

    :param mail: Reference to the parent QueuedMail.
    :type mail: QueuedMail

    :param email: Email address of the recipient.
    :type email: str
    
    :param orders: List of order IDs associated with this recipient.
    :type orders: list[str]
    
    :param positions: List of order position IDs.
    :type positions: list[str]
    
    :param items: List of item IDs associated with this user.
    :type items: list[str]
    
    :param team: Team ID if this is a team recipient.
    :type team: int or None
    
    :param sent: Whether this recipient has been successfully sent the email.
    :type sent: bool
    
    :param error: Error message if sending failed.
    :type error: str or None
    """
    mail = models.ForeignKey(QueuedMail, on_delete=models.CASCADE, related_name="recipients")
    email = models.EmailField()
    orders = ArrayField(models.CharField(max_length=64), blank=True, default=list)
    positions = ArrayField(models.CharField(max_length=64), blank=True, default=list)
    items = ArrayField(models.CharField(max_length=64), blank=True, default=list)
    team = models.IntegerField(null=True, blank=True)
    sent = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("mail", "email")

    def __str__(self):
        return f"{self.email} for {self.mail_id}"


class QueuedMailFilter(models.Model):
    """
    Stores structured filtering rules for recipient selection in QueuedMail.

    :param mail: Associated QueuedMail.
    :type mail: QueuedMail
    
    :param recipients: Target recipient scope: 'orders', 'attendees', or 'both'.
    :type recipients: str
    
    :param sendto: Email roles or tags to include.
    :type sendto: list[str]
    
    :param items: Filter by item IDs.
    :type items: list[int]
    
    :param checkin_lists: Check-in list IDs to filter by.
    :type checkin_lists: list[int]
    
    :param filter_checkins: Whether to filter based on check-in status.
    :type filter_checkins: bool
    
    :param not_checked_in: Whether to include only recipients who haven’t checked in.
    :type not_checked_in: bool
    
    :param subevent: Specific subevent ID to target.
    :type subevent: int or None
    
    :param subevents_from: Filter subevents from this date/time onward.
    :type subevents_from: datetime or None
    
    :param subevents_to: Filter subevents up to this date/time.
    :type subevents_to: datetime or None
    
    :param created_from: Include orders created after this date/time.
    :type created_from: datetime or None
    
    :param created_to: Include orders created before this date/time.
    :type created_to: datetime or None
    
    :param orders: Explicit order IDs to include.
    :type orders: list[int]
    
    :param teams: Team IDs to include (for team-based emails).
    :type teams: list[int]
    """
    mail = models.OneToOneField(QueuedMail, on_delete=models.CASCADE, related_name="filters_data")

    recipients = models.CharField(
        max_length=10,
        choices=[("orders", "Orders"), ("attendees", "Attendees"), ("both", "Both")],
        default="orders",
        blank=True
    )
    sendto = ArrayField(models.CharField(max_length=20), blank=True, default=list)
    items = ArrayField(models.IntegerField(), blank=True, default=list)
    checkin_lists = ArrayField(models.IntegerField(), blank=True, default=list)
    filter_checkins = models.BooleanField(default=False)
    not_checked_in = models.BooleanField(default=False)
    subevent = models.IntegerField(null=True, blank=True)
    subevents_from = models.DateTimeField(null=True, blank=True)
    subevents_to = models.DateTimeField(null=True, blank=True)
    created_from = models.DateTimeField(null=True, blank=True)
    created_to = models.DateTimeField(null=True, blank=True)
    orders = ArrayField(models.IntegerField(), blank=True, default=list)
    teams = ArrayField(models.IntegerField(), blank=True, default=list)

    def __str__(self):
        return f"Filters for mail {self.mail_id}"
