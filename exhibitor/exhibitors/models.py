import os
import secrets
import string
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pretix.base.models import Event


def generate_key():
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))

def generate_booth_id():
    import string
    import random
    
    # Generate a random booth_id if none exists
    characters = string.ascii_letters + string.digits
    while True:
        booth_id = ''.join(random.choices(characters, k=8))  # 8-character random string
        if not ExhibitorInfo.objects.filter(booth_id=booth_id).exists():
            return booth_id


def exhibitor_logo_path(instance, filename):
    return os.path.join('exhibitors', 'logos', instance.name, filename)

class ExhibitorSettings(models.Model):
    event = models.ForeignKey('pretixbase.Event', on_delete=models.CASCADE)
    exhibitors_access_mail_subject = models.CharField(max_length=255)
    exhibitors_access_mail_body = models.TextField()
    allowed_fields = models.JSONField(default=list)

    @property
    def all_allowed_fields(self):
        """Return all allowed fields, including required default fields"""
        default_fields = ['attendee_name', 'attendee_email']
        return list(set(default_fields + self.allowed_fields))

    class Meta:
        pass

class ExhibitorInfo(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(
        max_length=190,
        verbose_name=_('Name')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        null=True,
        blank=True
    )
    url = models.URLField(
        verbose_name=_('URL'),
        null=True,
        blank=True
    )
    email = models.EmailField(
        verbose_name=_('Email'),
        null=True,
        blank=True
    )
    logo = models.ImageField(
        upload_to=exhibitor_logo_path,
        null=True,
        blank=True
    )
    key = models.CharField(
        max_length=8,
        default=generate_key,
    )
    booth_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('BoothName'),
    )
    lead_scanning_enabled = models.BooleanField(
        default=False
    )
    allow_voucher_access = models.BooleanField(default=False)
    allow_lead_access = models.BooleanField(default=False)
    lead_scanning_scope_by_device = models.BooleanField(default=False)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

class ExhibitorItem(models.Model):
    # If no ExhibitorItem exists => use default
    # If ExhibitorItem exists with layout=None => don't print
    item = models.OneToOneField('pretixbase.Item', null=True, blank=True, related_name='exhibitor_assignment',
                                on_delete=models.CASCADE)
    exhibitor = models.ForeignKey('ExhibitorInfo', on_delete=models.CASCADE, related_name='item_assignments',
                                  null=True, blank=True)

    class Meta:
        ordering = ('id',)


class Lead(models.Model):
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE
    )
    exhibitor_name = models.CharField(
        max_length=190
    )
    pseudonymization_id = models.CharField(
        max_length=190
    )
    scanned = models.DateTimeField()
    scan_type = models.CharField(
        max_length=50
    )
    device_name = models.CharField(
        max_length=50
    )
    attendee = models.JSONField(
        null=True,
        blank=True
    ) 
    booth_id = models.CharField(
        max_length=100,
        editable=True
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('BoothName'),
    )

    def __str__(self):
        return f"Lead scanned by {self.exhibitor.name}"

class ExhibitorTag(models.Model):
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    name = models.CharField(max_length=50)
    use_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exhibitor', 'name')
        ordering = ['-use_count', 'name']

    def __str__(self):
        return f"{self.name} ({self.exhibitor.name})"
