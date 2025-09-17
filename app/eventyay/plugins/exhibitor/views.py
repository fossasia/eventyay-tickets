from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from rest_framework import status, views
from rest_framework.response import Response

from eventyay.control.permissions import EventPermissionRequiredMixin

from .forms import ExhibitorInfoForm, ExhibitorSettingsForm
from .models import ExhibitorInfo, ExhibitorSettings, Lead
from .permissions import ExhibitorKeyPermission, LeadAccessPermission
from .services import ExhibitorKeyService, LeadService


# Control/Admin Views
class ExhibitorListView(EventPermissionRequiredMixin, ListView):
    """List view for exhibitors in the control panel."""
    model = ExhibitorInfo
    template_name = 'exhibitor/list.html'
    context_object_name = 'exhibitors'
    permission = 'can_change_event_settings'
    paginate_by = 20
    
    def get_queryset(self):
        return ExhibitorInfo.objects.filter(
            event=self.request.event,
            is_active=True
        ).order_by('sort_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_exhibitors'] = self.get_queryset().count()
        context['total_leads'] = Lead.objects.filter(
            exhibitor__event=self.request.event
        ).count()
        return context


class ExhibitorDetailView(EventPermissionRequiredMixin, DetailView):
    """Detail view for a single exhibitor."""
    model = ExhibitorInfo
    template_name = 'exhibitor/detail.html'
    context_object_name = 'exhibitor'
    permission = 'can_change_event_settings'
    
    def get_queryset(self):
        return ExhibitorInfo.objects.filter(event=self.request.event)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exhibitor = self.get_object()
        context['lead_stats'] = LeadService.get_lead_statistics(exhibitor)
        context['recent_leads'] = exhibitor.leads.order_by('-scanned')[:10]
        return context


class ExhibitorCreateView(EventPermissionRequiredMixin, CreateView):
    """Create view for new exhibitors."""
    model = ExhibitorInfo
    form_class = ExhibitorInfoForm
    template_name = 'exhibitor/form.html'
    permission = 'can_change_event_settings'
    
    def form_valid(self, form):
        form.instance.event = self.request.event
        
        # Generate booth_id if not provided
        if not form.cleaned_data.get('booth_id'):
            from .services import BoothIdService
            form.instance.booth_id = BoothIdService.generate_booth_id()
        
        messages.success(self.request, _('Exhibitor created successfully.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('plugins:exhibitor:detail', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
            'pk': self.object.pk
        })


class ExhibitorEditView(EventPermissionRequiredMixin, UpdateView):
    """Edit view for existing exhibitors."""
    model = ExhibitorInfo
    form_class = ExhibitorInfoForm
    template_name = 'exhibitor/form.html'
    permission = 'can_change_event_settings'
    
    def get_queryset(self):
        return ExhibitorInfo.objects.filter(event=self.request.event)
    
    def form_valid(self, form):
        messages.success(self.request, _('Exhibitor updated successfully.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('plugins:exhibitor:detail', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
            'pk': self.object.pk
        })


class ExhibitorDeleteView(EventPermissionRequiredMixin, DeleteView):
    """Delete view for exhibitors."""
    model = ExhibitorInfo
    template_name = 'exhibitor/delete.html'
    permission = 'can_change_event_settings'
    
    def get_queryset(self):
        return ExhibitorInfo.objects.filter(event=self.request.event)
    
    def delete(self, request, *args, **kwargs):
        # Soft delete by setting is_active to False
        self.object = self.get_object()
        self.object.is_active = False
        self.object.save()
        messages.success(request, _('Exhibitor deleted successfully.'))
        return redirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('plugins:exhibitor:list', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorCopyKeyView(EventPermissionRequiredMixin, View):
    """View to copy exhibitor access key."""
    permission = 'can_change_event_settings'
    
    def get(self, request, *args, **kwargs):
        exhibitor = get_object_or_404(
            ExhibitorInfo,
            pk=kwargs['pk'],
            event=request.event
        )
        
        response = HttpResponse(exhibitor.key, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="exhibitor_{exhibitor.id}_key.txt"'
        return response


class ExhibitorSettingsView(EventPermissionRequiredMixin, UpdateView):
    """Settings view for exhibitor configuration."""
    model = ExhibitorSettings
    form_class = ExhibitorSettingsForm
    template_name = 'exhibitor/settings.html'
    permission = 'can_change_event_settings'
    
    def get_object(self, queryset=None):
        obj, created = ExhibitorSettings.objects.get_or_create(
            event=self.request.event
        )
        return obj
    
    def form_valid(self, form):
        messages.success(self.request, _('Settings saved successfully.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('plugins:exhibitor:settings', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class LeadListView(EventPermissionRequiredMixin, ListView):
    """List view for leads in the control panel."""
    model = Lead
    template_name = 'exhibitor/leads.html'
    context_object_name = 'leads'
    permission = 'can_change_event_settings'
    paginate_by = 50
    
    def get_queryset(self):
        return Lead.objects.filter(
            exhibitor__event=self.request.event
        ).select_related('exhibitor').order_by('-scanned')


class LeadExportView(EventPermissionRequiredMixin, View):
    """Export leads to CSV."""
    permission = 'can_change_event_settings'
    
    def get(self, request, *args, **kwargs):
        # This would implement CSV export functionality
        # Placeholder for now
        return HttpResponse("CSV export not implemented yet", content_type='text/plain')


# API Views
class ExhibitorAuthView(views.APIView):
    """API view for exhibitor authentication."""
    
    def post(self, request, *args, **kwargs):
        from .serializers import ExhibitorAuthSerializer
        
        serializer = ExhibitorAuthSerializer(data=request.data)
        if serializer.is_valid():
            exhibitor = serializer.exhibitor
            return Response({
                'success': True,
                'exhibitor_id': exhibitor.id,
                'exhibitor_name': exhibitor.name,
                'booth_id': exhibitor.booth_id,
                'booth_name': exhibitor.booth_name,
                'lead_scanning_enabled': exhibitor.lead_scanning_enabled,
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': 'Invalid credentials',
            'details': serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)


class ExhibitorAPIListView(views.APIView):
    """API view for listing exhibitors."""
    
    def get(self, request, *args, **kwargs):
        from .serializers import ExhibitorInfoPublicSerializer
        from django.db.models import Q
        
        # Get query parameters
        search = request.GET.get('search', '')
        featured_only = request.GET.get('featured', '').lower() == 'true'
        
        # Build queryset
        queryset = ExhibitorInfo.objects.filter(
            event=request.event,
            is_active=True
        )
        
        if featured_only:
            queryset = queryset.filter(featured=True)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(booth_name__icontains=search)
            )
        
        queryset = queryset.order_by('sort_order', 'name')
        
        # Serialize data
        serializer = ExhibitorInfoPublicSerializer(
            queryset, 
            many=True, 
            context={'request': request}
        )
        
        return Response({
            'success': True,
            'count': queryset.count(),
            'exhibitors': serializer.data
        })


class ExhibitorAPIDetailView(views.APIView):
    """API view for exhibitor details."""
    
    def get(self, request, pk, *args, **kwargs):
        from .serializers import ExhibitorInfoPublicSerializer
        
        try:
            exhibitor = ExhibitorInfo.objects.get(
                pk=pk,
                event=request.event,
                is_active=True
            )
            
            serializer = ExhibitorInfoPublicSerializer(
                exhibitor,
                context={'request': request}
            )
            
            return Response({
                'success': True,
                'exhibitor': serializer.data
            })
            
        except ExhibitorInfo.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Exhibitor not found'
            }, status=status.HTTP_404_NOT_FOUND)


class LeadCreateView(views.APIView):
    """API view for creating leads from scanned attendees."""
    permission_classes = [LeadAccessPermission]
    
    def post(self, request, *args, **kwargs):
        from .serializers import LeadCreateSerializer, LeadSerializer
        from .services import LeadService, AttendeeDataService
        from eventyay.base.models import OrderPosition
        
        serializer = LeadCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid parameters',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        exhibitor = request.exhibitor
        
        try:
            # Get exhibitor settings
            settings, _ = ExhibitorSettings.objects.get_or_create(
                event=exhibitor.event
            )
            
            # Get attendee details
            if data['open_event']:
                order_position = OrderPosition.objects.get(
                    secret=data['lead']
                )
            else:
                order_position = OrderPosition.objects.get(
                    pseudonymization_id=data['lead']
                )
            
            # Get allowed attendee data
            attendee_data = AttendeeDataService.get_allowed_attendee_data(
                order_position, settings, exhibitor
            )
            
            # Create lead
            lead = LeadService.create_lead(
                exhibitor=exhibitor,
                attendee_data=attendee_data,
                scan_data={
                    'pseudonymization_id': data['lead'],
                    'scan_type': data['scan_type'],
                    'device_name': data['device_name']
                }
            )
            
            # Serialize response
            lead_serializer = LeadSerializer(lead)
            
            return Response({
                'success': True,
                'lead_id': lead.id,
                'lead': lead_serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except OrderPosition.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Attendee not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except ValidationError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_409_CONFLICT)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LeadRetrieveView(views.APIView):
    """API view for retrieving exhibitor leads."""
    permission_classes = [ExhibitorKeyPermission]
    
    def get(self, request, *args, **kwargs):
        from .serializers import LeadSerializer
        from django.core.paginator import Paginator
        
        exhibitor = request.exhibitor
        
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 50)), 100)
        status_filter = request.GET.get('status', '')
        search = request.GET.get('search', '')
        
        # Build queryset
        queryset = Lead.objects.filter(exhibitor=exhibitor)
        
        if status_filter:
            queryset = queryset.filter(follow_up_status=status_filter)
        
        if search:
            # Search in attendee data
            queryset = queryset.filter(
                models.Q(attendee__name__icontains=search) |
                models.Q(attendee__email__icontains=search) |
                models.Q(notes__icontains=search)
            )
        
        queryset = queryset.order_by('-scanned')
        
        # Paginate
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # Serialize
        serializer = LeadSerializer(page_obj.object_list, many=True)
        
        return Response({
            'success': True,
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'leads': serializer.data
        })


class LeadUpdateView(views.APIView):
    """API view for updating lead information."""
    permission_classes = [LeadAccessPermission]
    
    def post(self, request, lead_id, *args, **kwargs):
        from .serializers import LeadUpdateSerializer, LeadSerializer
        from .services import LeadService
        
        try:
            lead = Lead.objects.get(
                pseudonymization_id=lead_id,
                exhibitor=request.exhibitor
            )
        except Lead.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Lead not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LeadUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid parameters',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Update lead
        if 'note' in data or 'tags' in data:
            LeadService.update_lead_notes(
                lead,
                data.get('note', lead.notes),
                data.get('tags')
            )
        
        if 'follow_up_status' in data:
            lead.update_follow_up_status(data['follow_up_status'])
        
        # Return updated lead
        lead_serializer = LeadSerializer(lead)
        
        return Response({
            'success': True,
            'lead': lead_serializer.data
        })


class TagListView(views.APIView):
    """API view for listing exhibitor tags."""
    permission_classes = [ExhibitorKeyPermission]
    
    def get(self, request, *args, **kwargs):
        from .serializers import ExhibitorTagSerializer
        
        exhibitor = request.exhibitor
        tags = ExhibitorTag.objects.filter(exhibitor=exhibitor).order_by('-use_count', 'name')
        
        serializer = ExhibitorTagSerializer(tags, many=True)
        
        return Response({
            'success': True,
            'tags': [tag['name'] for tag in serializer.data],
            'tag_details': serializer.data
        })