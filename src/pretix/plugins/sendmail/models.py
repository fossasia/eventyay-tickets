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

class QueuedMail(models.Model):
    """
    Stores queued emails composed by organizers for later sending.
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="queued_mails")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    to_users = models.JSONField(null=True, blank=True)

    raw_subject = I18nTextField(null=True, blank=True)
    raw_message = I18nTextField(null=True, blank=True)

    # Recipient type: "orders", "attendees", or "both"
    recipients = models.CharField(
        max_length=20,
        choices=[
            ("orders", "Orders only"),
            ("attendees", "Attendees only"),
            ("both", "Orders and Attendees"),
        ],
        default="orders",
    )

    filters = models.JSONField(null=True, blank=True)

    reply_to = models.CharField(max_length=1000, null=True, blank=True)
    bcc = models.TextField(null=True, blank=True)  # comma-separated
    locale = models.CharField(max_length=16, null=True, blank=True)
    attachments = models.JSONField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"QueuedMail(event={self.event.slug}, subject={self.raw_subject[:30]}, sent={self.sent})"
    

    @property
    def subject_en(self):
        """
        Returns English subject string from raw_subject.
        Handles both JSON and Python-dict-style strings.
        """
        try:
            # If already a dict (unlikely but safe)
            if isinstance(self.raw_subject, dict):
                return self.raw_subject.get('en', '')

            # Try JSON decode
            data = json.loads(self.raw_subject)
            return data.get('en', '')

        except (TypeError, ValueError, json.JSONDecodeError):
            try:
                # Fallback: Python literal eval for single-quoted dict
                data = ast.literal_eval(self.raw_subject)
                if isinstance(data, dict):
                    return data.get('en', '')
            except (ValueError, SyntaxError):
                pass

        # Fallback to raw string
        return self.raw_subject or ''


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
        if self.sent:
            return  # Already sent

        if not self.to_users:
            return False  # Nothing to send

        subject = LazyI18nString(self.raw_subject)
        message = LazyI18nString(self.raw_message)

        changed = False

        from pretix.base.services.mail import SendMailException
        for recipient in self.to_users:
            if recipient.get("sent"):
                continue  # Already sent

            email = recipient.get("email")
            orders = recipient.get("orders")
            order_id = orders[0] if orders else None

            positions = recipient.get("positions")
            position_id = positions[0] if positions else None

            sender = self.event.settings.get('mail_from') if self.event else None

            try:
                order = Order.objects.get(pk=order_id, event=self.event) if order_id else None
                position = OrderPosition.objects.get(pk=position_id) if position_id else None

                # Get fallback invoice address
                try:
                    ia = order.invoice_address if order else None
                except InvoiceAddress.DoesNotExist:
                    ia = InvoiceAddress(order=order) if order else None

                position_or_address = position or ia

                try:
                    context = get_email_context(
                        event=self.event,
                        order=order,
                        position=position,
                        position_or_address=position_or_address,
                    )
                except Exception as e:
                    logger.exception("Error while generating email context")
                    recipient["error"] = f"Context error: {str(e)}"
                    continue

                mail(
                    email=email,
                    subject=subject,
                    template=message,
                    context=context,
                    event=self.event,
                    locale=order.locale if order else self.locale,
                    order=order,
                    position=position,
                    sender=sender,
                    attach_cached_files=self.attachments,
                    user=self.user,
                    auto_email=False,
                )

                recipient["sent"] = True
                recipient["error"] = None
                changed = True

            except SendMailException as e:
                recipient["error"] = str(e)
                recipient["sent"] = False
                changed = True

            except Exception as e:
                recipient["error"] = f"Internal error: {str(e)}"
                recipient["sent"] = False
                changed = True

        if changed:
            self.sent = all(r.get("sent", False) for r in self.to_users)
            self.sent_at = now() if self.sent else None
            self.save(update_fields=["to_users", "sent", "sent_at"])

        return True

    def render_preview(self):
        """
        Returns a dict of locale -> {subject, html body}
        using fake placeholder context
        """
        from pretix.base.email import get_available_placeholders
        from pretix.base.templatetags.rich_text import markdown_compile_email

        output = {}
        for locale in self.event.settings.locales:
            with language(locale, self.event.settings.region):
                context_dict = TolerantDict()
                for k, v in get_available_placeholders(
                    self.event, ['event', 'order', 'position_or_address']
                ).items():
                    context_dict[k] = v.render_sample(self.event)

                subject = bleach.clean(self.subject_localized(locale), tags=[])
                preview_subject = subject.format_map(context_dict)
                message = self.message_localized(locale)
                preview_text = markdown_compile_email(message.format_map(context_dict))

                output[locale] = {
                    'subject': preview_subject,
                    'html': preview_text,
                }
        return output

    def get_recipient_emails(self):
        """
        Resolve and return the full list of unique email addresses
        this queued mail will send to.
        """
        emails = set()

        orders_qs = Order.objects.filter(
            pk__in=self.filters.get('orders', []),
            event=self.event
        )

        if self.recipients in ("both", "attendees"):
            for order in orders_qs:
                positions = order.positions.prefetch_related('addons')
                for pos in positions:
                    if pos.attendee_email:
                        emails.add(pos.attendee_email.strip().lower())

        if self.recipients in ("both", "orders"):
            for order in orders_qs:
                if order.email:
                    emails.add(order.email.strip().lower())

        return sorted(emails)


    def populate_to_users(self, save=True):
        """
        Resolves recipients and populates `to_users` with grouped metadata.
        """
        from collections import defaultdict
        recipients = defaultdict(lambda: {"orders": set(), "positions": set(), "items": set()})

        orders_qs = Order.objects.filter(pk__in=self.filters.get('orders', []), event=self.event)

        if self.recipients in ("both", "attendees"):
            for order in orders_qs:
                for pos in order.positions.prefetch_related('item', 'addons'):
                    if pos.attendee_email:
                        email = pos.attendee_email.strip().lower()
                        recipients[email]["orders"].add(str(order.pk))
                        recipients[email]["positions"].add(str(pos.pk))
                        recipients[email]["items"].add(str(pos.item.pk))

        if self.recipients in ("both", "orders"):
            for order in orders_qs:
                if order.email:
                    email = order.email.strip().lower()
                    recipients[email]["orders"].add(str(order.pk))
                    recipients[email]["items"].update(
                        str(item_id) for item_id in order.positions.values_list('item__pk', flat=True)
                    )

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
