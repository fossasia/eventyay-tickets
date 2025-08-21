from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from eventyay.base.models import Event
from .models import (
    ExhibitorInfo, ExhibitorSettings, ExhibitorStaff,
    ExhibitorLink, Lead, ExhibitorTag, ContactRequest
)
from .serializers import (
    ExhibitorListSerializer, ExhibitorDetailSerializer,
    ExhibitorCreateUpdateSerializer, ExhibitorSettingsSerializer,
    ContactRequestCreateSerializer, ContactRequestSerializer,
    LeadSerializer, ExhibitorAnalyticsSerializer
)
from .filters import ExhibitorFilter
from .permissions import ExhibitorPermission


class ExhibitorViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exhibitors"""
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ExhibitorFilter
    search_fields = ['name', 'tagline', 'description', 'booth_name']
    ordering_fields = ['name', 'sort_order', 'created_at', 'featured']
    ordering = ['sort_order', 'name']
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter exhibitors by event and active status"""
        event_slug = self.kwargs.get('event_slug')
        org_slug = self.kwargs.get('org_slug')
        
        if event_slug and org_slug:
            event = get_object_or_404(Event, slug=event_slug, organizer__slug=org_slug)
            queryset = ExhibitorInfo.objects.filter(event=event)
        else:
            queryset = ExhibitorInfo.objects.all()
        
        # For public access, only show active exhibitors
        if self.action in ['list', 'retrieve'] and not self.request.user.is_authenticated:
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('event').prefetch_related(
            'staff__user', 'links', 'tags', 'leads', 'contact_requests'
        )
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ExhibitorListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ExhibitorCreateUpdateSerializer
        else:
            return ExhibitorDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, ExhibitorPermission]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def contact(self, request, pk=None):
        """Handle contact form submissions"""
        exhibitor = self.get_object()
        
        if not exhibitor.contact_enabled:
            return Response(
                {'error': 'Contact form is disabled for this exhibitor'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ContactRequestCreateSerializer(data=request.data)
        if serializer.is_valid():
            contact_request = serializer.save(exhibitor=exhibitor)
            
            # Create a lead entry for contact form submission
            Lead.objects.create(
                exhibitor=exhibitor,
                exhibitor_name=exhibitor.name,
                pseudonymization_id=f"contact_{contact_request.id}",
                scanned=timezone.now(),
                scan_type='contact_form',
                device_name='web_form',
                booth_id=exhibitor.booth_id,
                booth_name=exhibitor.booth_name,
                attendee={
                    'name': contact_request.attendee_name,
                    'email': contact_request.attendee_email
                },
                notes=f"Contact form: {contact_request.subject}"
            )
            
            return Response(
                ContactRequestSerializer(contact_request).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def analytics(self, request, pk=None):
        """Get analytics data for an exhibitor"""
        exhibitor = self.get_object()
        
        # Check if user has permission to view analytics
        if not request.user.is_staff and not exhibitor.staff.filter(user=request.user).exists():
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Calculate analytics
        total_leads = exhibitor.leads.count()
        total_contact_requests = exhibitor.contact_requests.count()
        
        # Leads by type
        leads_by_type = dict(
            exhibitor.leads.values('scan_type').annotate(count=Count('id')).values_list('scan_type', 'count')
        )
        
        # Leads by day (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        leads_by_day = {}
        for i in range(30):
            day = thirty_days_ago + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            count = exhibitor.leads.filter(
                scanned__date=day.date()
            ).count()
            leads_by_day[day_str] = count
        
        # Contact requests by status
        contact_requests_by_status = dict(
            exhibitor.contact_requests.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        # Top devices
        top_devices = list(
            exhibitor.leads.values('device_name').annotate(
                count=Count('id')
            ).order_by('-count')[:5].values_list('device_name', 'count')
        )
        
        # Simple engagement score (leads + contact requests)
        engagement_score = total_leads + (total_contact_requests * 2)
        
        analytics_data = {
            'total_leads': total_leads,
            'total_contact_requests': total_contact_requests,
            'leads_by_type': leads_by_type,
            'leads_by_day': leads_by_day,
            'contact_requests_by_status': contact_requests_by_status,
            'top_devices': top_devices,
            'engagement_score': float(engagement_score)
        }
        
        serializer = ExhibitorAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def leads(self, request, pk=None):
        """Get leads for an exhibitor"""
        exhibitor = self.get_object()
        
        # Check permissions
        if not request.user.is_staff and not exhibitor.staff.filter(
            user=request.user, can_manage_leads=True
        ).exists():
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        leads = exhibitor.leads.all().order_by('-scanned')
        serializer = LeadSerializer(leads, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def contact_requests(self, request, pk=None):
        """Get contact requests for an exhibitor"""
        exhibitor = self.get_object()
        
        # Check permissions
        if not request.user.is_staff and not exhibitor.staff.filter(user=request.user).exists():
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        contact_requests = exhibitor.contact_requests.all().order_by('-created_at')
        serializer = ContactRequestSerializer(contact_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured exhibitors"""
        queryset = self.get_queryset().filter(featured=True, is_active=True)
        serializer = ExhibitorListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced search for exhibitors"""
        queryset = self.get_queryset().filter(is_active=True)
        
        # Apply filters
        query = request.query_params.get('q', '')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(tagline__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct()
        
        # Filter by tags
        tags = request.query_params.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__name__in=tags).distinct()
        
        # Filter by category (if we add categories later)
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(tags__name=category)
        
        serializer = ExhibitorListSerializer(queryset, many=True)
        return Response(serializer.data)


class ExhibitorSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exhibitor settings"""
    serializer_class = ExhibitorSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter settings by event"""
        event_slug = self.kwargs.get('event_slug')
        org_slug = self.kwargs.get('org_slug')
        
        if event_slug and org_slug:
            event = get_object_or_404(Event, slug=event_slug, organizer__slug=org_slug)
            return ExhibitorSettings.objects.filter(event=event)
        
        return ExhibitorSettings.objects.none()


class ContactRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing contact requests"""
    serializer_class = ContactRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'exhibitor']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter contact requests by event and permissions"""
        event_slug = self.kwargs.get('event_slug')
        org_slug = self.kwargs.get('org_slug')
        
        if event_slug and org_slug:
            event = get_object_or_404(Event, slug=event_slug, organizer__slug=org_slug)
            queryset = ContactRequest.objects.filter(exhibitor__event=event)
        else:
            queryset = ContactRequest.objects.all()
        
        # Filter by user permissions
        if not self.request.user.is_staff:
            # Only show contact requests for exhibitors the user is staff of
            queryset = queryset.filter(
                exhibitor__staff__user=self.request.user
            )
        
        return queryset.select_related('exhibitor')


class LeadViewSet(viewsets.ModelViewSet):
    """ViewSet for managing leads"""
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['scan_type', 'follow_up_required', 'exhibitor']
    ordering_fields = ['scanned', 'follow_up_required']
    ordering = ['-scanned']
    
    def get_queryset(self):
        """Filter leads by event and permissions"""
        event_slug = self.kwargs.get('event_slug')
        org_slug = self.kwargs.get('org_slug')
        
        if event_slug and org_slug:
            event = get_object_or_404(Event, slug=event_slug, organizer__slug=org_slug)
            queryset = Lead.objects.filter(exhibitor__event=event)
        else:
            queryset = Lead.objects.all()
        
        # Filter by user permissions
        if not self.request.user.is_staff:
            # Only show leads for exhibitors the user can manage
            queryset = queryset.filter(
                exhibitor__staff__user=self.request.user,
                exhibitor__staff__can_manage_leads=True
            )
        
        return queryset.select_related('exhibitor')