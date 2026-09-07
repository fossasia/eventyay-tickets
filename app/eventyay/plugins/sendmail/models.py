import logging
from collections import defaultdict

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nTextField

from eventyay.base.email import get_email_context
from eventyay.mail.context import get_mail_context
from eventyay.base.models.auth import User
from eventyay.base.models.event import Event
from eventyay.base.models.orders import InvoiceAddress, Order, OrderPosition
from eventyay.base.i18n import LazyI18nString
from eventyay.base.services.mail import mail, SendMailException as MailTransportError
from eventyay.common.exceptions import SendMailException


logger = logging.getLogger(__name__)


class ComposingFor(models.TextChoices):
    ATTENDEES = 'attendees', 'Attendees'
    TEAMS = 'teams', 'Teams'


class Recipients(models.TextChoices):
    ORDERS = 'orders', 'Orders'
    ATTENDEES = 'attendees', 'Attendees'
    BOTH = 'both', 'Both'
    INDIVIDUAL = 'individual', 'Individual'



class EmailQueue(models.Model):
    """
    Stores queued emails composed by organizers for later sending.

    :param event: The event this queued mail is associated with.
    :type event: Event
    :param user: The user (organizer/admin) who queued this email.
    :type user: User

    :param composing_for: To whom the organizer is composing email for. Either "attendees" or "teams"
    :type composing_for: str

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
    :type created: datetime.datetime

    :param updated: Timestamp of the last update.
    :type updated: datetime.datetime

    :param sent_at: When the email was sent (fully completed).
    :type sent_at: datetime.datetime or None
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="email_queue")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    composing_for = models.CharField(max_length=20, choices=ComposingFor.choices, default=ComposingFor.ATTENDEES)

    subject = I18nTextField(null=True, blank=True)
    message = I18nTextField(null=True, blank=True)

    reply_to = models.CharField(max_length=100, default='', blank=True)
    bcc = models.TextField(null=True, blank=True)  # comma-separated
    locale = models.CharField(max_length=16, blank=True, default='')
    attachments = ArrayField(base_field=models.UUIDField(), blank=True, default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=_('If set, the email will be sent at this time instead of immediately.'),
    )
    is_draft = models.BooleanField(
        default=False,
        verbose_name=_('Draft'),
        help_text=_('Drafts are kept out of the outbox and are never sent until they are moved there.')
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"EmailQueue(event={self.event.slug}, sent_at={self.sent_at})"

    @property
    def email_type_display(self):
        if self.composing_for == ComposingFor.TEAMS:
            return _('Team members')
        return _('Attendees, orders, tickets')

    def get_edit_url(self):
        if self.composing_for == ComposingFor.TEAMS:
            return reverse('control:event.mail.compose_teams', kwargs={
                'organizer': self.event.organizer.slug,
                'event': self.event.slug
            }) + f'?draft={self.pk}'
        return reverse('control:event.mail.send', kwargs={
            'organizer': self.event.organizer.slug,
            'event': self.event.slug
        }) + f'?draft={self.pk}'

    def duplicate(self):
        """
        Creates a copy of this EmailQueue as a draft and copies its filter data and recipients.
        """
        new_mail = EmailQueue.objects.create(
            event=self.event,
            user=self.user,
            composing_for=self.composing_for,
            subject=self.subject,
            message=self.message,
            reply_to=self.reply_to,
            bcc=self.bcc,
            locale=self.locale,
            attachments=list(self.attachments),
            scheduled_at=self.scheduled_at,
            is_draft=True,
            sent_at=None,
        )

        if hasattr(self, 'filters_data'):
            orig_filter = self.filters_data
            EmailQueueFilter.objects.create(
                mail=new_mail,
                recipients=orig_filter.recipients,
                order_status=list(orig_filter.order_status),
                products=list(orig_filter.products),
                checkin_lists=list(orig_filter.checkin_lists),
                has_filter_checkins=orig_filter.has_filter_checkins,
                not_checked_in=orig_filter.not_checked_in,
                subevent=orig_filter.subevent,
                subevents_from=orig_filter.subevents_from,
                subevents_to=orig_filter.subevents_to,
                order_created_from=orig_filter.order_created_from,
                order_created_to=orig_filter.order_created_to,
                orders=list(orig_filter.orders),
                teams=list(orig_filter.teams),
                team_role=orig_filter.team_role,
                permission_level=orig_filter.permission_level,
                status=orig_filter.status,
                specific_people=list(orig_filter.specific_people),
                exclude_me=orig_filter.exclude_me,
                individual_attendees=list(getattr(orig_filter, 'individual_attendees', []) or []),
            )

        recipients = [
            EmailQueueToUser(
                mail=new_mail,
                email=r.email,
                orders=list(r.orders),
                positions=list(r.positions),
                products=list(r.products),
                team=r.team,
                sent=False,
                error=None,
            )
            for r in self.recipients.all()
        ]
        if recipients:
            EmailQueueToUser.objects.bulk_create(recipients)

        return new_mail

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
            return False  # Already sent

        if self.is_draft:
            return False  # Do not send drafts

        if self.scheduled_at and self.scheduled_at > now():
            raise SendMailException(_('This email is scheduled for the future and cannot be sent yet.'))

        recipients = self.recipients.all()
        if not recipients.exists():
            if self.scheduled_at is not None:
                self.scheduled_at = None
                self.save(update_fields=['scheduled_at'])
            return False

        subject = LazyI18nString(self.subject)
        message = LazyI18nString(self.message)

        for recipient in recipients:
            if recipient.sent:
                continue
            self._send_to_recipient(recipient, subject, message, async_send=async_send)

        self._finalize_send_status()
        return True

    def _build_email_context(self, order, position, position_or_address, recipient):
        try:
            if self.composing_for != ComposingFor.ATTENDEES:
                user_obj = User.objects.filter(email__iexact=recipient.email).first()
                ctx = get_email_context(event=self.event, user=user_obj)
                ctx.update(get_mail_context(event=self.event, user=user_obj))
                return ctx

            # Only pass keys that are present. ``position=None`` still counts as
            # provided to get_email_context and would break position placeholders.
            if order is not None and position is None:
                positions = list(
                    order.positions.select_related('product', 'order__event').order_by('positionid')
                )
                position = next((pos for pos in positions if pos.generate_ticket), None) or (
                    positions[0] if positions else None
                )
                position_or_address = position_or_address or position

            kwargs = {'event': self.event}
            if order is not None:
                kwargs['order'] = order
            if position is not None:
                kwargs['position'] = position
            if position_or_address is not None:
                kwargs['position_or_address'] = position_or_address
            return get_email_context(**kwargs)
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.exception('Error while generating email context')
            recipient.error = f'Context error: {e}'
            recipient.save(update_fields=['error'])
            return None

    def _finalize_send_status(self):
        self.sent_at = now() if all(r.sent for r in self.recipients.all()) else None
        # Clear scheduled_at after the first send attempt so the periodic poller
        # does not keep picking this row up when some recipients permanently
        # failed (bounces, invalid addresses). Users can still retry failed
        # recipients manually from the outbox.
        self.scheduled_at = None
        self.save(update_fields=["sent_at", "scheduled_at"])

    def _send_to_recipient(self, recipient, subject, message, async_send=True):
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
                sync_send=not async_send,
            )
            recipient.sent = True
            recipient.error = None
            recipient.save(update_fields=["sent", "error"])
        except MailTransportError as se:
            recipient.sent = False
            recipient.error = str(se)
            recipient.save(update_fields=["sent", "error"])
            logger.exception("Mail transport error while sending to %s", email)
        except Exception as e:
            recipient.sent = False
            recipient.error = f"Internal error: {str(e)}"
            recipient.save(update_fields=["sent", "error"])
            logger.exception("Unexpected error while sending to %s", email)

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

        filters = getattr(self, 'filters_data', None)
        if not filters:
            return

        recipients_mode = filters.recipients or "orders"
        orders_qs = Order.objects.filter(
            pk__in=filters.orders,
            event=self.event
        ).prefetch_related('positions__product', 'positions__addons', 'positions__checkins')

        recipients = defaultdict(lambda: {
            "orders": set(),
            "positions": set(),
            "products": set()
        })

        for order in orders_qs:
            order_fallback_needed = False
            attendee_found = False
            individual_positions = set(filters.individual_attendees) if recipients_mode == "individual" else None

            for pos in order.positions.all():
                if individual_positions is not None and pos.pk not in individual_positions:
                    continue
                if pos.attendee_email:
                    attendee_found = True
                    email = pos.attendee_email.strip().lower()
                    recipients[email]["orders"].add(order.pk)
                    recipients[email]["positions"].add(pos.pk)
                    recipients[email]["products"].add(pos.product.pk)
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
                recipients[email]["orders"].add(order.pk)
                for pos in order.positions.all():
                    recipients[email]["positions"].add(pos.pk)
                    recipients[email]["products"].add(pos.product_id)

            # Explicit inclusion of orders (include positions so QR/attendee
            # placeholders can resolve for buyer/order contact emails).
            if recipients_mode in ("both", "orders") and order.email:
                email = order.email.strip().lower()
                recipients[email]["orders"].add(order.pk)
                for pos in order.positions.all():
                    recipients[email]["positions"].add(pos.pk)
                    recipients[email]["products"].add(pos.product_id)

        # Clear and insert fresh records
        self.recipients.all().delete()

        objs = [
            EmailQueueToUser(
                mail=self,
                email=email,
                orders=list(data["orders"]),
                positions=list(data["positions"]),
                products=list(data["products"]),
                sent=False,
                error=None,
            )
            for email, data in recipients.items()
        ]

        EmailQueueToUser.objects.bulk_create(objs)
        if save:
            self.save()


class EmailQueueToUser(models.Model):
    """
    Represents a single recipient of a EmailQueue.

    :param mail: Reference to the parent EmailQueue.
    :type mail: EmailQueue

    :param email: Email address of the recipient.
    :type email: email
    
    :param orders: List of order IDs associated with this recipient.
    :type orders: list[int]
    
    :param positions: List of order position IDs.
    :type positions: list[int]
    
    :param products: List of product IDs associated with this user.
    :type products: list[int]
    
    :param team: Team ID if this is a team recipient.
    :type team: int or None
    
    :param sent: Whether this recipient has been successfully sent the email.
    :type sent: bool
    
    :param error: Error message if sending failed.
    :type error: str or None
    """
    mail = models.ForeignKey(EmailQueue, on_delete=models.CASCADE, related_name="recipients")
    email = models.EmailField()
    orders = ArrayField(models.BigIntegerField(), blank=True, default=list)
    positions = ArrayField(models.BigIntegerField(), blank=True, default=list)
    products = ArrayField(models.BigIntegerField(), blank=True, default=list)
    team = models.IntegerField(null=True, blank=True)
    sent = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("mail", "email")

    def __str__(self):
        return f"{self.email} for {self.mail_id}"


class EmailQueueFilter(models.Model):
    """
    Stores structured filtering rules for recipient selection in EmailQueue.

    :param mail: Associated EmailQueue.
    :type mail: EmailQueue
    
    :param recipients: Target recipient scope: 'orders', 'attendees', or 'both'.
    :type recipients: str
    
    :param order_status: Email roles or tags to include.
    :type order_status: list[str]
    
    :param products: Filter by product IDs.
    :type products: list[int]
    
    :param checkin_lists: Check-in list IDs to filter by.
    :type checkin_lists: list[int]
    
    :param has_filter_checkins: Whether to filter based on check-in status.
    :type has_filter_checkins: bool
    
    :param not_checked_in: Whether to include only recipients who haven’t checked in.
    :type not_checked_in: bool
    
    :param subevent: Specific subevent ID to target.
    :type subevent: int or None
    
    :param subevents_from: Filter subevents from this date/time onward.
    :type subevents_from: datetime.datetime or None
    
    :param subevents_to: Filter subevents up to this date/time.
    :type subevents_to: datetime.datetime or None
    
    :param order_created_from: Include orders created after this date/time.
    :type order_created_from: datetime.datetime or None
    
    :param order_created_to: Include orders created before this date/time.
    :type order_created_to: datetime.datetime or None
    
    :param orders: Explicit order IDs to include.
    :type orders: list[int]
    
    :param teams: Team IDs to include (for team-based emails).
    :type teams: list[int]
    """
    mail = models.OneToOneField(EmailQueue, on_delete=models.CASCADE, related_name="filters_data")

    recipients = models.CharField(max_length=10, choices=Recipients.choices, default=Recipients.ORDERS, blank=True)
    order_status = ArrayField(models.CharField(max_length=20), blank=True, default=list)
    products = ArrayField(models.BigIntegerField(), blank=True, default=list)
    checkin_lists = ArrayField(models.IntegerField(), blank=True, default=list)
    has_filter_checkins = models.BooleanField(default=False)
    not_checked_in = models.BooleanField(default=False)
    subevent = models.IntegerField(null=True, blank=True)
    subevents_from = models.DateTimeField(null=True, blank=True)
    subevents_to = models.DateTimeField(null=True, blank=True)
    order_created_from = models.DateTimeField(null=True, blank=True)
    order_created_to = models.DateTimeField(null=True, blank=True)
    orders = ArrayField(models.IntegerField(), blank=True, default=list)

    teams = ArrayField(models.IntegerField(), blank=True, default=list)
    team_role = models.CharField(max_length=20, blank=True, default='')
    permission_level = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=10, blank=True, default='')
    specific_people = ArrayField(models.IntegerField(), blank=True, default=list)
    exclude_me = models.BooleanField(default=False)

    individual_attendees = ArrayField(models.IntegerField(), blank=True, default=list)

    def __str__(self):
        return f"Filters for mail {self.mail_id}"
