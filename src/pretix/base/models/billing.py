from datetime import date

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from pretix.base.models import LoggedModel


class BillingInvoice(LoggedModel):
    STATUS_PENDING = "n"
    STATUS_PAID = "p"
    STATUS_EXPIRED = "e"
    STATUS_CANCELED = "c"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("pending")),
        (STATUS_PAID, _("paid")),
        (STATUS_EXPIRED, _("expired")),
        (STATUS_CANCELED, _("canceled")),
    ]

    organizer = models.ForeignKey('Organizer', on_delete=models.CASCADE)
    # organizer_billing = models.ForeignKey('OrganizerBilling', on_delete=models.CASCADE)
    event = models.ForeignKey('Event', on_delete=models.CASCADE)

    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)

    ticket_fee = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, null=True, blank=True)
    paid_datetime = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    monthly_bill = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=50)

    last_reminder_datetime = models.DateTimeField(null=True, blank=True)
    next_reminder_datetime = models.DateTimeField(null=True, blank=True)
    reminder_schedule = ArrayField(
        models.IntegerField(),
        default=list,  # Sets the default to an empty list
        blank=True,
        help_text="Days after creation for reminders, e.g., [14, 28]"
    )
    reminder_enabled = models.BooleanField(default=True)

    objects = ScopedManager(organizer='organizer')

    class Meta:
        verbose_name = "Billing Invoice"
        verbose_name_plural = "Billing Invoices"
        ordering = ("-created_at",)
