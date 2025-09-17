"""
Serializers for the exhibitor plugin API.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import ExhibitorInfo, ExhibitorSettings, Lead, ExhibitorTag, ExhibitorItem


class ExhibitorInfoSerializer(serializers.ModelSerializer):
    """Serializer for ExhibitorInfo model."""
    
    logo_url = serializers.SerializerMethodField()
    lead_count = serializers.SerializerMethodField()
    recent_leads_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'id', 'name', 'description', 'url', 'email', 'logo_url',
            'booth_id', 'booth_name', 'lead_scanning_enabled',
            'allow_voucher_access', 'allow_lead_access',
            'lead_scanning_scope_by_device', 'is_active', 'sort_order',
            'featured', 'lead_count', 'recent_leads_count', 'created', 'modified'
        ]
        read_only_fields = ['id', 'logo_url', 'lead_count', 'recent_leads_count', 'created', 'modified']
    
    def get_logo_url(self, obj):
        """Get the full URL for the exhibitor logo."""
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    
    def get_lead_count(self, obj):
        """Get total number of leads for this exhibitor."""
        return obj.lead_count
    
    def get_recent_leads_count(self, obj):
        """Get number of recent leads (last 7 days)."""
        return obj.recent_leads_count
    
    def validate_name(self, value):
        """Validate exhibitor name."""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError(
                _('Exhibitor name must be at least 2 characters long.')
            )
        return value.strip()
    
    def validate_booth_id(self, value):
        """Validate booth ID uniqueness."""
        if value:
            # Check for uniqueness, excluding current instance
            queryset = ExhibitorInfo.objects.filter(booth_id=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise serializers.ValidationError(
                    _('This booth ID is already in use.')
                )
        
        return value


class ExhibitorInfoPublicSerializer(serializers.ModelSerializer):
    """Public serializer for ExhibitorInfo (limited fields)."""
    
    logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'id', 'name', 'description', 'url', 'logo_url',
            'booth_id', 'booth_name', 'featured'
        ]
    
    def get_logo_url(self, obj):
        """Get the full URL for the exhibitor logo."""
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None


class ExhibitorAuthSerializer(serializers.Serializer):
    """Serializer for exhibitor authentication."""
    
    key = serializers.CharField(
        max_length=8,
        min_length=8,
        help_text=_('Exhibitor access key')
    )
    
    def validate_key(self, value):
        """Validate the exhibitor key."""
        try:
            exhibitor = ExhibitorInfo.objects.get(key=value, is_active=True)
            self.exhibitor = exhibitor
            return value
        except ExhibitorInfo.DoesNotExist:
            raise serializers.ValidationError(_('Invalid exhibitor key.'))


class LeadSerializer(serializers.ModelSerializer):
    """Serializer for Lead model."""
    
    attendee_name = serializers.SerializerMethodField()
    attendee_email = serializers.SerializerMethodField()
    attendee_company = serializers.SerializerMethodField()
    exhibitor_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'exhibitor_name', 'pseudonymization_id', 'scanned',
            'scan_type', 'device_name', 'booth_id', 'booth_name',
            'attendee_name', 'attendee_email', 'attendee_company',
            'notes', 'follow_up_status', 'follow_up_date', 'created', 'modified'
        ]
        read_only_fields = [
            'id', 'exhibitor_name', 'pseudonymization_id', 'scanned',
            'scan_type', 'device_name', 'booth_id', 'booth_name',
            'attendee_name', 'attendee_email', 'attendee_company',
            'created', 'modified'
        ]
    
    def get_attendee_name(self, obj):
        """Get attendee name from stored data."""
        return obj.get_attendee_name()
    
    def get_attendee_email(self, obj):
        """Get attendee email from stored data."""
        return obj.get_attendee_email()
    
    def get_attendee_company(self, obj):
        """Get attendee company from stored data."""
        if obj.attendee and 'company' in obj.attendee:
            return obj.attendee['company']
        return None


class LeadCreateSerializer(serializers.Serializer):
    """Serializer for creating leads from scanned attendees."""
    
    lead = serializers.CharField(
        max_length=190,
        help_text=_('Pseudonymization ID or secret of the attendee')
    )
    scanned = serializers.DateTimeField(
        help_text=_('Timestamp when the attendee was scanned')
    )
    scan_type = serializers.CharField(
        max_length=50,
        default='manual',
        help_text=_('Type of scan (qr, manual, etc.)')
    )
    device_name = serializers.CharField(
        max_length=50,
        help_text=_('Name of the device used for scanning')
    )
    open_event = serializers.BooleanField(
        default=False,
        help_text=_('Whether this is an open event (uses secret instead of pseudonymization_id)')
    )


class LeadUpdateSerializer(serializers.Serializer):
    """Serializer for updating lead information."""
    
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_('Note about this lead')
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        help_text=_('Tags to associate with this lead')
    )
    follow_up_status = serializers.ChoiceField(
        choices=Lead.FOLLOW_UP_CHOICES,
        required=False,
        help_text=_('Follow-up status for this lead')
    )


class ExhibitorTagSerializer(serializers.ModelSerializer):
    """Serializer for ExhibitorTag model."""
    
    class Meta:
        model = ExhibitorTag
        fields = ['id', 'name', 'use_count', 'created', 'modified']
        read_only_fields = ['id', 'use_count', 'created', 'modified']


class ExhibitorSettingsSerializer(serializers.ModelSerializer):
    """Serializer for ExhibitorSettings model."""
    
    all_allowed_fields = serializers.ReadOnlyField()
    
    class Meta:
        model = ExhibitorSettings
        fields = [
            'id', 'exhibitors_access_mail_subject', 'exhibitors_access_mail_body',
            'allowed_fields', 'all_allowed_fields', 'enable_public_directory',
            'enable_lead_export', 'lead_retention_days'
        ]
        read_only_fields = ['id', 'all_allowed_fields']
    
    def validate_lead_retention_days(self, value):
        """Validate lead retention period."""
        if value < 1 or value > 3650:
            raise serializers.ValidationError(
                _('Lead retention period must be between 1 and 3650 days.')
            )
        return value


class ExhibitorItemSerializer(serializers.ModelSerializer):
    """Serializer for ExhibitorItem model."""
    
    item_name = serializers.CharField(source='item.name', read_only=True)
    exhibitor_name = serializers.CharField(source='exhibitor.name', read_only=True)
    
    class Meta:
        model = ExhibitorItem
        fields = ['id', 'item', 'item_name', 'exhibitor', 'exhibitor_name']
        read_only_fields = ['id', 'item_name', 'exhibitor_name']


class ExhibitorStatsSerializer(serializers.Serializer):
    """Serializer for exhibitor statistics."""
    
    total_leads = serializers.IntegerField()
    leads_today = serializers.IntegerField()
    leads_this_week = serializers.IntegerField()
    follow_up_pending = serializers.IntegerField()
    follow_up_contacted = serializers.IntegerField()
    follow_up_qualified = serializers.IntegerField()
    follow_up_converted = serializers.IntegerField()


class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions on exhibitors."""
    
    ACTION_CHOICES = [
        ('enable_lead_scanning', _('Enable lead scanning')),
        ('disable_lead_scanning', _('Disable lead scanning')),
        ('regenerate_keys', _('Regenerate access keys')),
        ('export_data', _('Export exhibitor data')),
    ]
    
    action = serializers.ChoiceField(
        choices=ACTION_CHOICES,
        help_text=_('Action to perform on selected exhibitors')
    )
    exhibitor_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text=_('List of exhibitor IDs to perform action on')
    )
    
    def validate_exhibitor_ids(self, value):
        """Validate that all exhibitor IDs exist and are accessible."""
        if not value:
            raise serializers.ValidationError(_('At least one exhibitor must be selected.'))
        
        # Check that all exhibitors exist and are accessible
        request = self.context.get('request')
        if request and hasattr(request, 'event'):
            existing_ids = ExhibitorInfo.objects.filter(
                id__in=value,
                event=request.event,
                is_active=True
            ).values_list('id', flat=True)
            
            missing_ids = set(value) - set(existing_ids)
            if missing_ids:
                raise serializers.ValidationError(
                    _('Invalid exhibitor IDs: {}').format(', '.join(map(str, missing_ids)))
                )
        
        return value