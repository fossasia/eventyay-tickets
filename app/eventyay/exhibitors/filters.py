import django_filters
from django.db.models import Q
from .models import ExhibitorInfo, Lead, ContactRequest


class ExhibitorFilter(django_filters.FilterSet):
    """Filter set for exhibitor queries"""
    name = django_filters.CharFilter(lookup_expr='icontains')
    featured = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    contact_enabled = django_filters.BooleanFilter()
    lead_scanning_enabled = django_filters.BooleanFilter()
    tags = django_filters.CharFilter(method='filter_by_tags')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = ExhibitorInfo
        fields = {
            'name': ['exact', 'icontains'],
            'featured': ['exact'],
            'is_active': ['exact'],
            'contact_enabled': ['exact'],
            'lead_scanning_enabled': ['exact'],
            'created_at': ['gte', 'lte'],
            'sort_order': ['gte', 'lte'],
        }
    
    def filter_by_tags(self, queryset, name, value):
        """Filter by tag names (comma-separated)"""
        if value:
            tag_names = [tag.strip() for tag in value.split(',')]
            return queryset.filter(tags__name__in=tag_names).distinct()
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Full-text search across multiple fields"""
        if value:
            return queryset.filter(
                Q(name__icontains=value) |
                Q(tagline__icontains=value) |
                Q(description__icontains=value) |
                Q(booth_name__icontains=value) |
                Q(tags__name__icontains=value)
            ).distinct()
        return queryset


class LeadFilter(django_filters.FilterSet):
    """Filter set for lead queries"""
    exhibitor_name = django_filters.CharFilter(lookup_expr='icontains')
    scan_type = django_filters.ChoiceFilter(choices=Lead.SCAN_TYPE_CHOICES)
    scanned_date = django_filters.DateFilter(field_name='scanned', lookup_expr='date')
    scanned_after = django_filters.DateTimeFilter(field_name='scanned', lookup_expr='gte')
    scanned_before = django_filters.DateTimeFilter(field_name='scanned', lookup_expr='lte')
    device_name = django_filters.CharFilter(lookup_expr='icontains')
    follow_up_required = django_filters.BooleanFilter()
    
    class Meta:
        model = Lead
        fields = {
            'exhibitor': ['exact'],
            'scan_type': ['exact'],
            'follow_up_required': ['exact'],
            'scanned': ['gte', 'lte', 'date'],
        }


class ContactRequestFilter(django_filters.FilterSet):
    """Filter set for contact request queries"""
    attendee_name = django_filters.CharFilter(lookup_expr='icontains')
    attendee_email = django_filters.CharFilter(lookup_expr='icontains')
    subject = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.ChoiceFilter(choices=ContactRequest.STATUS_CHOICES)
    created_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = ContactRequest
        fields = {
            'exhibitor': ['exact'],
            'status': ['exact'],
            'created_at': ['gte', 'lte', 'date'],
        }