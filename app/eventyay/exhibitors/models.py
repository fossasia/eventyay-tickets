import os
import secrets
import string
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from eventyay.base.models import Event


def generate_booth_id():
    """Generate unique booth ID"""
    characters = string.ascii_letters + string.digits
    while True:
        booth_id = ''.join(secrets.choice(characters) for _ in range(8))
        if not ExhibitorInfo.objects.filter(booth_id=booth_id).exists():
            return booth_id


def generate_api_key():
    """Generate API key for exhibitor authentication"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))


def exhibitor_logo_path(instance, filename):
    """Generate upload path for exhibitor logos"""
    return f'exhibitors/{instance.event.slug}/logos/{instance.booth_id}/{filename}'


def exhibitor_banner_path(instance, filename):
    """Generate upload path for exhibitor banners"""
    return f'exhibitors/{instance.event.slug}/banners/{instance.booth_id}/{filename}'


class ExhibitorSettings(models.Model):
    """Global exhibitor settings per event"""
    event = models.OneToOneField(
        Event, 
        on_delete=models.CASCADE, 
        related_name='exhibitor_settings'
    )
    directory_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Enable Exhibitor Directory')
    )
    contact_form_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Enable Contact Forms')
    )
    lead_scanning_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Enable Lead Scanning')
    )
    allowed_contact_fields = models.JSONField(
        default=list,
        help_text=_('Additional fields allowed in contact forms')
    )
    exhibitors_access_mail_subject = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Access Email Subject')
    )
    exhibitors_access_mail_body = models.TextField(
        blank=True,
        verbose_name=_('Access Email Body')
    )
    
    class Meta:
        verbose_name = _('Exhibitor Settings')
        verbose_name_plural = _('Exhibitor Settings')
    
    def __str__(self):
        return f'Exhibitor Settings for {self.event.name}'
    
    @property
    def all_allowed_contact_fields(self):
        """Return all allowed fields including required defaults"""
        default_fields = ['attendee_name', 'attendee_email']
        return list(set(default_fields + self.allowed_contact_fields))


class ExhibitorInfo(models.Model):
    """Main exhibitor information model"""
    # Basic Information
    event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name='exhibitors'
    )
    name = models.CharField(
        max_length=190, 
        verbose_name=_('Exhibitor Name')
    )
    tagline = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_('Tagline')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    # Contact Information
    url = models.URLField(
        blank=True,
        verbose_name=_('Website URL')
    )
    email = models.EmailField(
        blank=True,
        verbose_name=_('Contact Email')
    )
    
    # Media
    logo = models.ImageField(
        upload_to=exhibitor_logo_path,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        verbose_name=_('Logo')
    )
    banner = models.ImageField(
        upload_to=exhibitor_banner_path,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp', 'mp4', 'webm'])],
        verbose_name=_('Banner/Video')
    )
    
    # Booth Information
    booth_id = models.CharField(
        max_length=100,
        unique=True,
        default=generate_booth_id,
        verbose_name=_('Booth ID')
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('Booth Name')
    )
    
    # Integration Fields
    highlighted_room_id = models.CharField(
        max_length=100, 
        blank=True,
        help_text=_('Video room ID for virtual booth')
    )
    api_key = models.CharField(
        max_length=16,
        default=generate_api_key,
        unique=True,
        verbose_name=_('API Key')
    )
    
    # Features
    contact_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Enable Contact Form')
    )
    lead_scanning_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Enable Lead Scanning')
    )
    allow_voucher_access = models.BooleanField(
        default=False,
        verbose_name=_('Allow Voucher Access')
    )
    allow_lead_access = models.BooleanField(
        default=False,
        verbose_name=_('Allow Lead Access')
    )
    lead_scanning_scope_by_device = models.BooleanField(
        default=False,
        verbose_name=_('Scope Lead Scanning by Device')
    )
    
    # Status and Ordering
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    featured = models.BooleanField(
        default=False,
        verbose_name=_('Featured')
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = _('Exhibitor')
        verbose_name_plural = _('Exhibitors')
        indexes = [
            models.Index(fields=['event', 'is_active']),
            models.Index(fields=['booth_id']),
            models.Index(fields=['featured']),
        ]
    
    def __str__(self):
        return f'{self.name} ({self.booth_id})'
    
    def save(self, *args, **kwargs):
        if not self.booth_name:
            self.booth_name = f'Booth {self.booth_id}'
        super().save(*args, **kwargs)


class ExhibitorStaff(models.Model):
    """Staff members assigned to exhibitors"""
    exhibitor = models.ForeignKey(
        ExhibitorInfo, 
        on_delete=models.CASCADE, 
        related_name='staff'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE
    )
    role = models.CharField(
        max_length=50, 
        default='staff',
        choices=[
            ('admin', _('Administrator')),
            ('staff', _('Staff Member')),
            ('representative', _('Representative')),
        ],
        verbose_name=_('Role')
    )
    can_manage_leads = models.BooleanField(
        default=True,
        verbose_name=_('Can Manage Leads')
    )
    can_edit_info = models.BooleanField(
        default=False,
        verbose_name=_('Can Edit Exhibitor Info')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['exhibitor', 'user']
        verbose_name = _('Exhibitor Staff')
        verbose_name_plural = _('Exhibitor Staff')
    
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.exhibitor.name}'


class ExhibitorLink(models.Model):
    """External links for exhibitors"""
    CATEGORY_CHOICES = [
        ('profile', _('Profile')),
        ('download', _('Download')),
        ('social', _('Social Media')),
        ('video', _('Video')),
        ('external', _('External Link')),
    ]
    
    exhibitor = models.ForeignKey(
        ExhibitorInfo, 
        on_delete=models.CASCADE, 
        related_name='links'
    )
    url = models.URLField(verbose_name=_('URL'))
    display_text = models.CharField(
        max_length=100,
        verbose_name=_('Display Text')
    )
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES,
        verbose_name=_('Category')
    )
    sorting_priority = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    
    class Meta:
        ordering = ['sorting_priority', 'display_text']
        verbose_name = _('Exhibitor Link')
        verbose_name_plural = _('Exhibitor Links')
    
    def __str__(self):
        return f'{self.display_text} ({self.exhibitor.name})'


class Lead(models.Model):
    """Lead tracking for exhibitor interactions"""
    SCAN_TYPE_CHOICES = [
        ('qr_code', _('QR Code')),
        ('manual', _('Manual Entry')),
        ('contact_form', _('Contact Form')),
        ('booth_visit', _('Booth Visit')),
    ]
    
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='leads'
    )
    exhibitor_name = models.CharField(
        max_length=190,
        verbose_name=_('Exhibitor Name')
    )
    pseudonymization_id = models.CharField(
        max_length=190,
        verbose_name=_('Attendee ID')
    )
    scanned = models.DateTimeField(verbose_name=_('Scan Time'))
    scan_type = models.CharField(
        max_length=50,
        choices=SCAN_TYPE_CHOICES,
        verbose_name=_('Scan Type')
    )
    device_name = models.CharField(
        max_length=50,
        verbose_name=_('Device Name')
    )
    attendee = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Attendee Data')
    )
    booth_id = models.CharField(
        max_length=100,
        verbose_name=_('Booth ID')
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('Booth Name')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    follow_up_required = models.BooleanField(
        default=False,
        verbose_name=_('Follow-up Required')
    )
    
    class Meta:
        ordering = ['-scanned']
        verbose_name = _('Lead')
        verbose_name_plural = _('Leads')
        indexes = [
            models.Index(fields=['exhibitor', 'scanned']),
            models.Index(fields=['pseudonymization_id']),
        ]
    
    def __str__(self):
        return f'Lead for {self.exhibitor.name} - {self.scanned}'


class ExhibitorTag(models.Model):
    """Tags for categorizing exhibitors"""
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    name = models.CharField(
        max_length=50,
        verbose_name=_('Tag Name')
    )
    use_count = models.IntegerField(
        default=0,
        verbose_name=_('Use Count')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['exhibitor', 'name']
        ordering = ['-use_count', 'name']
        verbose_name = _('Exhibitor Tag')
        verbose_name_plural = _('Exhibitor Tags')
    
    def __str__(self):
        return f'{self.name} ({self.exhibitor.name})'


class ContactRequest(models.Model):
    """Contact requests from attendees to exhibitors"""
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('responded', _('Responded')),
        ('closed', _('Closed')),
    ]
    
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='contact_requests'
    )
    attendee_name = models.CharField(
        max_length=100,
        verbose_name=_('Attendee Name')
    )
    attendee_email = models.EmailField(
        verbose_name=_('Attendee Email')
    )
    subject = models.CharField(
        max_length=200,
        verbose_name=_('Subject')
    )
    message = models.TextField(
        verbose_name=_('Message')
    )
    additional_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Data')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Contact Request')
        verbose_name_plural = _('Contact Requests')
    
    def __str__(self):
        return f'Contact from {self.attendee_name} to {self.exhibitor.name}'