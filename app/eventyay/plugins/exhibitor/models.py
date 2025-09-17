import os
import secrets
import string
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from eventyay.base.models.base import LoggedModel
from eventyay.base.models.event import Event
from eventyay.base.models.product import Product


def generate_key():
    """Generate a secure random key for exhibitor authentication."""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


def generate_booth_id():
    """Generate a unique booth ID."""
    characters = string.ascii_letters + string.digits
    while True:
        booth_id = ''.join(secrets.choice(characters) for _ in range(8))
        if not ExhibitorInfo.objects.filter(booth_id=booth_id).exists():
            return booth_id


def exhibitor_logo_path(instance, filename):
    """Generate upload path for exhibitor logos."""
    return os.path.join('exhibitors', 'logos', str(instance.event.slug), instance.name, filename)


class ExhibitorSettings(LoggedModel):
    """Settings for exhibitor functionality per event."""
    
    event = models.OneToOneField(
        Event,
        on_delete=models.CASCADE,
        related_name='exhibitor_settings'
    )
    exhibitors_access_mail_subject = models.CharField(
        max_length=255,
        default=_('Your exhibitor access credentials'),
        verbose_name=_('Access email subject')
    )
    exhibitors_access_mail_body = models.TextField(
        default=_('Please find your exhibitor access credentials below.'),
        verbose_name=_('Access email body')
    )
    allowed_fields = models.JSONField(
        default=list,
        verbose_name=_('Allowed attendee fields'),
        help_text=_('Additional attendee fields that exhibitors can access')
    )
    
    # New enhanced settings
    enable_public_directory = models.BooleanField(
        default=True,
        verbose_name=_('Enable public exhibitor directory'),
        help_text=_('Allow public access to the exhibitor directory')
    )
    enable_lead_export = models.BooleanField(
        default=True,
        verbose_name=_('Enable lead data export'),
        help_text=_('Allow exhibitors to export their lead data')
    )
    lead_retention_days = models.IntegerField(
        default=365,
        verbose_name=_('Lead retention period (days)'),
        help_text=_('Number of days to retain lead data before automatic deletion')
    )
    
    objects = ScopedManager(organizer='event__organizer')
    
    class Meta:
        verbose_name = _('Exhibitor Settings')
        verbose_name_plural = _('Exhibitor Settings')
    
    @property
    def all_allowed_fields(self):
        """Return all allowed fields, including required default fields."""
        default_fields = ['attendee_name', 'attendee_email']
        return list(set(default_fields + (self.allowed_fields or [])))
    
    def __str__(self):
        return f"Exhibitor Settings for {self.event.name}"


class ExhibitorInfo(LoggedModel):
    """Main model for exhibitor information."""
    
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='exhibitors'
    )
    name = models.CharField(
        max_length=190,
        verbose_name=_('Name'),
        help_text=_('Name of the exhibiting organization')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        null=True,
        blank=True,
        help_text=_('Brief description of the exhibitor')
    )
    url = models.URLField(
        verbose_name=_('Website URL'),
        null=True,
        blank=True,
        help_text=_('Exhibitor website URL')
    )
    email = models.EmailField(
        verbose_name=_('Contact Email'),
        null=True,
        blank=True,
        help_text=_('Primary contact email for the exhibitor')
    )
    logo = models.ImageField(
        upload_to=exhibitor_logo_path,
        null=True,
        blank=True,
        verbose_name=_('Logo'),
        help_text=_('Exhibitor logo image')
    )
    key = models.CharField(
        max_length=8,
        default=generate_key,
        unique=True,
        verbose_name=_('Access Key'),
        help_text=_('Unique key for mobile app authentication')
    )
    booth_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('Booth ID'),
        help_text=_('Unique identifier for the booth')
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('Booth Name'),
        help_text=_('Display name for the booth (e.g., "Booth A1")')
    )
    
    # Lead scanning configuration
    lead_scanning_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Lead scanning enabled'),
        help_text=_('Allow this exhibitor to scan attendee badges')
    )
    allow_voucher_access = models.BooleanField(
        default=False,
        verbose_name=_('Allow voucher access'),
        help_text=_('Allow access to voucher information')
    )
    allow_lead_access = models.BooleanField(
        default=False,
        verbose_name=_('Allow lead access'),
        help_text=_('Allow access to lead management features')
    )
    lead_scanning_scope_by_device = models.BooleanField(
        default=False,
        verbose_name=_('Scope scanning by device'),
        help_text=_('Limit lead access to specific devices')
    )
    
    # Enhanced fields for enext integration
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this exhibitor is currently active')
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order'),
        help_text=_('Order for displaying exhibitors (lower numbers first)')
    )
    featured = models.BooleanField(
        default=False,
        verbose_name=_('Featured'),
        help_text=_('Mark this exhibitor as featured')
    )
    
    objects = ScopedManager(organizer='event__organizer')
    
    class Meta:
        verbose_name = _('Exhibitor')
        verbose_name_plural = _('Exhibitors')
        ordering = ('sort_order', 'name')
        indexes = [
            models.Index(fields=['event', 'is_active']),
            models.Index(fields=['booth_id']),
            models.Index(fields=['sort_order', 'name']),
            models.Index(fields=['featured', 'is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        if self.name and len(self.name.strip()) < 2:
            raise ValidationError({
                'name': _('Exhibitor name must be at least 2 characters long.')
            })
        
        if self.booth_id:
            # Check booth_id uniqueness
            queryset = ExhibitorInfo.objects.filter(booth_id=self.booth_id)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            if queryset.exists():
                raise ValidationError({
                    'booth_id': _('This booth ID is already in use.')
                })
    
    def save(self, *args, **kwargs):
        """Override save to generate booth_id if needed."""
        if not self.booth_id:
            self.booth_id = generate_booth_id()
        
        # Clean name
        if self.name:
            self.name = self.name.strip()
        
        super().save(*args, **kwargs)
    
    def regenerate_key(self):
        """Generate a new access key."""
        from .services import ExhibitorKeyService
        return ExhibitorKeyService.regenerate_key(self)
    
    @property
    def lead_count(self):
        """Get total number of leads for this exhibitor."""
        return self.leads.count()
    
    @property
    def recent_leads_count(self):
        """Get number of leads from the last 7 days."""
        from django.utils import timezone
        week_ago = timezone.now() - timezone.timedelta(days=7)
        return self.leads.filter(scanned__gte=week_ago).count()


class ExhibitorItem(LoggedModel):
    """Association between exhibitors and ticket items."""
    
    product = models.OneToOneField(
        Product,
        null=True,
        blank=True,
        related_name='exhibitor_assignment',
        on_delete=models.CASCADE,
        verbose_name=_('Product')
    )
    exhibitor = models.ForeignKey(
        'ExhibitorInfo',
        on_delete=models.CASCADE,
        related_name='item_assignments',
        null=True,
        blank=True,
        verbose_name=_('Exhibitor')
    )
    
    objects = ScopedManager(organizer='exhibitor__event__organizer')
    
    class Meta:
        verbose_name = _('Exhibitor Item Assignment')
        verbose_name_plural = _('Exhibitor Item Assignments')
        ordering = ('id',)
    
    def __str__(self):
        return f"{self.exhibitor.name} - {self.item.name if self.item else 'No Item'}"


class Lead(LoggedModel):
    """Model for storing scanned attendee leads."""
    
    FOLLOW_UP_CHOICES = [
        ('pending', _('Pending')),
        ('contacted', _('Contacted')),
        ('qualified', _('Qualified')),
        ('converted', _('Converted')),
    ]
    
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='leads',
        verbose_name=_('Exhibitor')
    )
    exhibitor_name = models.CharField(
        max_length=190,
        verbose_name=_('Exhibitor Name'),
        help_text=_('Name of the exhibitor at time of scan')
    )
    pseudonymization_id = models.CharField(
        max_length=190,
        verbose_name=_('Attendee ID'),
        help_text=_('Pseudonymized attendee identifier')
    )
    scanned = models.DateTimeField(
        verbose_name=_('Scanned At'),
        help_text=_('When the attendee was scanned')
    )
    scan_type = models.CharField(
        max_length=50,
        verbose_name=_('Scan Type'),
        help_text=_('Type of scan performed (QR, manual, etc.)')
    )
    device_name = models.CharField(
        max_length=50,
        verbose_name=_('Device Name'),
        help_text=_('Name of the device used for scanning')
    )
    attendee = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Attendee Data'),
        help_text=_('Stored attendee information based on privacy settings')
    )
    booth_id = models.CharField(
        max_length=100,
        verbose_name=_('Booth ID'),
        help_text=_('Booth ID at time of scan')
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('Booth Name'),
        help_text=_('Booth name at time of scan')
    )
    
    # Enhanced fields for better lead management
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this lead')
    )
    follow_up_status = models.CharField(
        max_length=20,
        choices=FOLLOW_UP_CHOICES,
        default='pending',
        verbose_name=_('Follow-up Status'),
        help_text=_('Current status of follow-up activities')
    )
    follow_up_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Follow-up Date'),
        help_text=_('When follow-up action was last taken')
    )
    
    objects = ScopedManager(organizer='exhibitor__event__organizer')
    
    class Meta:
        verbose_name = _('Lead')
        verbose_name_plural = _('Leads')
        unique_together = ('exhibitor', 'pseudonymization_id')
        ordering = ('-scanned',)
        indexes = [
            models.Index(fields=['exhibitor', 'scanned']),
            models.Index(fields=['follow_up_status']),
            models.Index(fields=['scanned']),
            models.Index(fields=['exhibitor', 'follow_up_status']),
        ]
    
    def __str__(self):
        attendee_name = self.get_attendee_name()
        return f"Lead: {attendee_name} -> {self.exhibitor.name}"
    
    def get_attendee_name(self):
        """Get attendee name from stored data."""
        if self.attendee and 'name' in self.attendee:
            return self.attendee['name']
        return f"Attendee {self.pseudonymization_id[:8]}"
    
    def get_attendee_email(self):
        """Get attendee email from stored data."""
        if self.attendee and 'email' in self.attendee:
            return self.attendee['email']
        return None
    
    def update_follow_up_status(self, status, notes=None):
        """Update follow-up status and optionally add notes."""
        from django.utils import timezone
        
        self.follow_up_status = status
        self.follow_up_date = timezone.now()
        
        if notes:
            self.notes = notes
        
        self.save(update_fields=['follow_up_status', 'follow_up_date', 'notes'])


class ExhibitorTag(LoggedModel):
    """Tags for categorizing exhibitors and leads."""
    
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='tags',
        verbose_name=_('Exhibitor')
    )
    name = models.CharField(
        max_length=50,
        verbose_name=_('Tag Name')
    )
    use_count = models.IntegerField(
        default=0,
        verbose_name=_('Usage Count'),
        help_text=_('Number of times this tag has been used')
    )
    
    objects = ScopedManager(organizer='exhibitor__event__organizer')
    
    class Meta:
        verbose_name = _('Exhibitor Tag')
        verbose_name_plural = _('Exhibitor Tags')
        unique_together = ('exhibitor', 'name')
        ordering = ['-use_count', 'name']
        indexes = [
            models.Index(fields=['exhibitor', 'use_count']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.exhibitor.name})"
    
    def increment_usage(self):
        """Increment the usage count for this tag."""
        self.use_count += 1
        self.save(update_fields=['use_count'])


# Signal handlers for model events
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver


@receiver(post_save, sender=ExhibitorInfo)
def exhibitor_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for exhibitors."""
    if created:
        # Log exhibitor creation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"New exhibitor created: {instance.name} (ID: {instance.id})")


@receiver(pre_delete, sender=ExhibitorInfo)
def exhibitor_pre_delete(sender, instance, **kwargs):
    """Handle pre-delete actions for exhibitors."""
    # Log exhibitor deletion
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Exhibitor being deleted: {instance.name} (ID: {instance.id})")


@receiver(post_save, sender=Lead)
def lead_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for leads."""
    if created:
        # Log lead creation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"New lead created for {instance.exhibitor.name}: {instance.get_attendee_name()}")