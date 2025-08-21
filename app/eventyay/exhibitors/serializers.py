from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    ExhibitorInfo, ExhibitorSettings, ExhibitorStaff,
    ExhibitorLink, Lead, ExhibitorTag, ContactRequest
)

User = get_user_model()


class ExhibitorStaffSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = ExhibitorStaff
        fields = [
            'id', 'user', 'user_name', 'user_email', 'user_avatar',
            'role', 'can_manage_leads', 'can_edit_info', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_user_avatar(self, obj):
        """Get user avatar URL if available"""
        if hasattr(obj.user, 'avatar') and obj.user.avatar:
            return obj.user.avatar.url
        return None


class ExhibitorLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExhibitorLink
        fields = [
            'id', 'url', 'display_text', 'category', 
            'sorting_priority', 'is_active'
        ]


class ExhibitorTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExhibitorTag
        fields = ['id', 'name', 'use_count', 'created_at']
        read_only_fields = ['use_count', 'created_at']


class ContactRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactRequest
        fields = [
            'id', 'attendee_name', 'attendee_email', 'subject', 
            'message', 'additional_data', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ContactRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating contact requests from public forms"""
    class Meta:
        model = ContactRequest
        fields = [
            'attendee_name', 'attendee_email', 'subject', 
            'message', 'additional_data'
        ]
    
    def validate_attendee_email(self, value):
        """Validate attendee email format"""
        if not value or '@' not in value:
            raise serializers.ValidationError("Please provide a valid email address.")
        return value


class LeadSerializer(serializers.ModelSerializer):
    exhibitor_name = serializers.CharField(read_only=True)
    booth_id = serializers.CharField(read_only=True)
    booth_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'exhibitor', 'exhibitor_name', 'pseudonymization_id',
            'scanned', 'scan_type', 'device_name', 'attendee',
            'booth_id', 'booth_name', 'notes', 'follow_up_required'
        ]
        read_only_fields = ['scanned', 'exhibitor_name', 'booth_id', 'booth_name']


class ExhibitorListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for exhibitor list views"""
    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    links_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'id', 'name', 'tagline', 'booth_id', 'booth_name',
            'logo_url', 'banner_url', 'featured', 'sort_order',
            'staff_count', 'links_count', 'contact_enabled'
        ]
    
    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None
    
    def get_banner_url(self, obj):
        if obj.banner:
            return obj.banner.url
        return None
    
    def get_staff_count(self, obj):
        return obj.staff.count()
    
    def get_links_count(self, obj):
        return obj.links.filter(is_active=True).count()


class ExhibitorDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for exhibitor detail views"""
    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    banner_is_video = serializers.SerializerMethodField()
    staff = ExhibitorStaffSerializer(many=True, read_only=True)
    links = ExhibitorLinkSerializer(many=True, read_only=True)
    tags = ExhibitorTagSerializer(many=True, read_only=True)
    social_links = serializers.SerializerMethodField()
    download_links = serializers.SerializerMethodField()
    external_links = serializers.SerializerMethodField()
    lead_count = serializers.SerializerMethodField()
    contact_requests_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'id', 'name', 'tagline', 'description', 'url', 'email',
            'logo_url', 'banner_url', 'banner_is_video', 'booth_id', 'booth_name',
            'highlighted_room_id', 'contact_enabled', 'is_active', 'featured',
            'sort_order', 'staff', 'links', 'tags', 'social_links',
            'download_links', 'external_links', 'lead_count', 
            'contact_requests_count', 'created_at', 'updated_at'
        ]
    
    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None
    
    def get_banner_url(self, obj):
        if obj.banner:
            return obj.banner.url
        return None
    
    def get_banner_is_video(self, obj):
        if obj.banner:
            return obj.banner.name.lower().endswith(('.mp4', '.webm', '.mov'))
        return False
    
    def get_social_links(self, obj):
        return ExhibitorLinkSerializer(
            obj.links.filter(category='social', is_active=True).order_by('sorting_priority'),
            many=True
        ).data
    
    def get_download_links(self, obj):
        return ExhibitorLinkSerializer(
            obj.links.filter(category='download', is_active=True).order_by('sorting_priority'),
            many=True
        ).data
    
    def get_external_links(self, obj):
        return ExhibitorLinkSerializer(
            obj.links.filter(category__in=['external', 'profile', 'video'], is_active=True).order_by('sorting_priority'),
            many=True
        ).data
    
    def get_lead_count(self, obj):
        return obj.leads.count()
    
    def get_contact_requests_count(self, obj):
        return obj.contact_requests.count()


class ExhibitorCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating exhibitors"""
    staff = ExhibitorStaffSerializer(many=True, required=False)
    links = ExhibitorLinkSerializer(many=True, required=False)
    tags = ExhibitorTagSerializer(many=True, required=False)
    
    class Meta:
        model = ExhibitorInfo
        fields = [
            'id', 'event', 'name', 'tagline', 'description', 'url', 'email',
            'logo', 'banner', 'booth_name', 'highlighted_room_id',
            'contact_enabled', 'lead_scanning_enabled', 'allow_voucher_access',
            'allow_lead_access', 'lead_scanning_scope_by_device',
            'is_active', 'featured', 'sort_order', 'staff', 'links', 'tags'
        ]
        read_only_fields = ['booth_id', 'api_key', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        staff_data = validated_data.pop('staff', [])
        links_data = validated_data.pop('links', [])
        tags_data = validated_data.pop('tags', [])
        
        exhibitor = ExhibitorInfo.objects.create(**validated_data)
        
        # Create related objects
        for staff_item in staff_data:
            ExhibitorStaff.objects.create(exhibitor=exhibitor, **staff_item)
        
        for link_item in links_data:
            ExhibitorLink.objects.create(exhibitor=exhibitor, **link_item)
        
        for tag_item in tags_data:
            ExhibitorTag.objects.create(exhibitor=exhibitor, **tag_item)
        
        return exhibitor
    
    def update(self, instance, validated_data):
        staff_data = validated_data.pop('staff', None)
        links_data = validated_data.pop('links', None)
        tags_data = validated_data.pop('tags', None)
        
        # Update main fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update related objects if provided
        if staff_data is not None:
            instance.staff.all().delete()
            for staff_item in staff_data:
                ExhibitorStaff.objects.create(exhibitor=instance, **staff_item)
        
        if links_data is not None:
            instance.links.all().delete()
            for link_item in links_data:
                ExhibitorLink.objects.create(exhibitor=instance, **link_item)
        
        if tags_data is not None:
            instance.tags.all().delete()
            for tag_item in tags_data:
                ExhibitorTag.objects.create(exhibitor=instance, **tag_item)
        
        return instance


class ExhibitorSettingsSerializer(serializers.ModelSerializer):
    """Serializer for exhibitor settings"""
    class Meta:
        model = ExhibitorSettings
        fields = [
            'id', 'event', 'directory_enabled', 'contact_form_enabled',
            'lead_scanning_enabled', 'allowed_contact_fields',
            'exhibitors_access_mail_subject', 'exhibitors_access_mail_body'
        ]


class ExhibitorAnalyticsSerializer(serializers.Serializer):
    """Serializer for exhibitor analytics data"""
    total_leads = serializers.IntegerField()
    total_contact_requests = serializers.IntegerField()
    leads_by_type = serializers.DictField()
    leads_by_day = serializers.DictField()
    contact_requests_by_status = serializers.DictField()
    top_devices = serializers.ListField()
    engagement_score = serializers.FloatField()