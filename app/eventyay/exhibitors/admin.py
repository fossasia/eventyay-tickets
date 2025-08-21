from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import (
    ExhibitorInfo, ExhibitorSettings, ExhibitorStaff, 
    ExhibitorLink, Lead, ExhibitorTag, ContactRequest
)


class ExhibitorStaffInline(admin.TabularInline):
    model = ExhibitorStaff
    extra = 0
    fields = ['user', 'role', 'can_manage_leads', 'can_edit_info']


class ExhibitorLinkInline(admin.TabularInline):
    model = ExhibitorLink
    extra = 0
    fields = ['url', 'display_text', 'category', 'sorting_priority', 'is_active']
    ordering = ['sorting_priority']


class ExhibitorTagInline(admin.TabularInline):
    model = ExhibitorTag
    extra = 0
    fields = ['name', 'use_count']
    readonly_fields = ['use_count']


@admin.register(ExhibitorInfo)
class ExhibitorInfoAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'booth_id', 'booth_name', 'event', 
        'is_active', 'featured', 'lead_count', 'created_at'
    ]
    list_filter = [
        'event', 'is_active', 'featured', 'contact_enabled', 
        'lead_scanning_enabled', 'created_at'
    ]
    search_fields = ['name', 'booth_id', 'booth_name', 'email']
    readonly_fields = ['api_key', 'created_at', 'updated_at', 'lead_count']
    
    fieldsets = [
        (_('Basic Information'), {
            'fields': ['event', 'name', 'tagline', 'description']
        }),
        (_('Contact Information'), {
            'fields': ['email', 'url']
        }),
        (_('Media'), {
            'fields': ['logo', 'banner']
        }),
        (_('Booth Information'), {
            'fields': ['booth_id', 'booth_name', 'highlighted_room_id']
        }),
        (_('Features'), {
            'fields': [
                'contact_enabled', 'lead_scanning_enabled', 
                'allow_voucher_access', 'allow_lead_access',
                'lead_scanning_scope_by_device'
            ]
        }),
        (_('Status'), {
            'fields': ['is_active', 'featured', 'sort_order']
        }),
        (_('System'), {
            'fields': ['api_key', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    inlines = [ExhibitorStaffInline, ExhibitorLinkInline, ExhibitorTagInline]
    
    def lead_count(self, obj):
        count = obj.leads.count()
        if count > 0:
            url = reverse('admin:exhibitors_lead_changelist')
            return format_html(
                '<a href="{}?exhibitor__id__exact={}">{} leads</a>',
                url, obj.id, count
            )
        return '0 leads'
    lead_count.short_description = _('Leads')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event')


@admin.register(ExhibitorSettings)
class ExhibitorSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'event', 'directory_enabled', 'contact_form_enabled', 
        'lead_scanning_enabled'
    ]
    list_filter = [
        'directory_enabled', 'contact_form_enabled', 'lead_scanning_enabled'
    ]
    
    fieldsets = [
        (_('General Settings'), {
            'fields': [
                'event', 'directory_enabled', 'contact_form_enabled', 
                'lead_scanning_enabled'
            ]
        }),
        (_('Contact Form Settings'), {
            'fields': [
                'allowed_contact_fields', 'exhibitors_access_mail_subject',
                'exhibitors_access_mail_body'
            ]
        })
    ]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'exhibitor_name', 'pseudonymization_id', 'scan_type', 
        'scanned', 'follow_up_required'
    ]
    list_filter = [
        'scan_type', 'follow_up_required', 'scanned', 
        'exhibitor__event'
    ]
    search_fields = [
        'exhibitor_name', 'pseudonymization_id', 'device_name'
    ]
    readonly_fields = ['scanned', 'attendee']
    
    fieldsets = [
        (_('Lead Information'), {
            'fields': [
                'exhibitor', 'exhibitor_name', 'pseudonymization_id',
                'scanned', 'scan_type', 'device_name'
            ]
        }),
        (_('Booth Information'), {
            'fields': ['booth_id', 'booth_name']
        }),
        (_('Follow-up'), {
            'fields': ['notes', 'follow_up_required']
        }),
        (_('Attendee Data'), {
            'fields': ['attendee'],
            'classes': ['collapse']
        })
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('exhibitor')


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = [
        'attendee_name', 'attendee_email', 'exhibitor', 
        'subject', 'status', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'exhibitor__event']
    search_fields = [
        'attendee_name', 'attendee_email', 'subject', 
        'exhibitor__name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        (_('Contact Information'), {
            'fields': [
                'exhibitor', 'attendee_name', 'attendee_email', 
                'subject', 'message'
            ]
        }),
        (_('Status'), {
            'fields': ['status', 'created_at', 'updated_at']
        }),
        (_('Additional Data'), {
            'fields': ['additional_data'],
            'classes': ['collapse']
        })
    ]


@admin.register(ExhibitorStaff)
class ExhibitorStaffAdmin(admin.ModelAdmin):
    list_display = ['user', 'exhibitor', 'role', 'can_manage_leads', 'can_edit_info']
    list_filter = ['role', 'can_manage_leads', 'can_edit_info', 'exhibitor__event']
    search_fields = ['user__username', 'user__email', 'exhibitor__name']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'exhibitor')


@admin.register(ExhibitorLink)
class ExhibitorLinkAdmin(admin.ModelAdmin):
    list_display = ['display_text', 'exhibitor', 'category', 'sorting_priority', 'is_active']
    list_filter = ['category', 'is_active', 'exhibitor__event']
    search_fields = ['display_text', 'url', 'exhibitor__name']
    ordering = ['exhibitor', 'sorting_priority']


@admin.register(ExhibitorTag)
class ExhibitorTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'exhibitor', 'use_count', 'created_at']
    list_filter = ['created_at', 'exhibitor__event']
    search_fields = ['name', 'exhibitor__name']
    readonly_fields = ['use_count', 'created_at']
    ordering = ['-use_count', 'name']