from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.db.models import Q, Count
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from eventyay.base.models import Event
from .models import ExhibitorInfo, ContactRequest, Lead
from .serializers import (
    ExhibitorListSerializer, ExhibitorDetailSerializer,
    ContactRequestCreateSerializer
)
from .forms import ExhibitorForm, ContactForm


class ExhibitorDirectoryView(TemplateView):
    """Main exhibitor directory page"""
    template_name = 'exhibitors/directory.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # For now, get all active exhibitors (can be filtered by event later)
        exhibitors = ExhibitorInfo.objects.filter(is_active=True)
        exhibitors = exhibitors.select_related('event').prefetch_related('staff', 'links', 'tags')
        
        # Get the first event if available (for context)
        event = None
        if exhibitors.exists():
            event = exhibitors.first().event
        
        # Apply filters
        search_query = self.request.GET.get('search', '')
        if search_query:
            exhibitors = exhibitors.filter(
                Q(name__icontains=search_query) |
                Q(tagline__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        featured_filter = self.request.GET.get('featured')
        if featured_filter == 'true':
            exhibitors = exhibitors.filter(featured=True)
        
        # Ordering
        order_by = self.request.GET.get('order_by', 'sort_order')
        if order_by in ['name', 'sort_order', 'created_at']:
            exhibitors = exhibitors.order_by(order_by, 'name')
        
        # Pagination
        paginator = Paginator(exhibitors, 12)  # 12 exhibitors per page
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get featured exhibitors for sidebar
        featured_exhibitors = ExhibitorInfo.objects.filter(
            is_active=True,
            featured=True
        )
        if event:
            featured_exhibitors = featured_exhibitors.filter(event=event)
        featured_exhibitors = featured_exhibitors[:6]
        
        context.update({
            'event': event,
            'exhibitors': page_obj,
            'featured_exhibitors': featured_exhibitors,
            'search_query': search_query,
            'total_count': paginator.count,
            'page_obj': page_obj,
        })
        
        return context


class ExhibitorDetailView(TemplateView):
    """Individual exhibitor detail page"""
    template_name = 'exhibitors/detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        booth_id = kwargs.get('booth_id')
        exhibitor = get_object_or_404(
            ExhibitorInfo,
            booth_id=booth_id,
            is_active=True
        )
        
        # Get related data
        staff = exhibitor.staff.select_related('user').all()
        links = exhibitor.links.filter(is_active=True).order_by('sorting_priority')
        tags = exhibitor.tags.all()
        
        # Categorize links
        social_links = links.filter(category='social')
        download_links = links.filter(category='download')
        external_links = links.filter(category__in=['external', 'profile', 'video'])
        
        # Check if banner is video
        banner_is_video = False
        if exhibitor.banner:
            banner_is_video = exhibitor.banner.name.lower().endswith(('.mp4', '.webm', '.mov'))
        
        context.update({
            'exhibitor': exhibitor,
            'staff': staff,
            'social_links': social_links,
            'download_links': download_links,
            'external_links': external_links,
            'tags': tags,
            'banner_is_video': banner_is_video,
            'contact_form': ContactForm(),
        })
        
        return context


class ExhibitorManagementView(LoginRequiredMixin, TemplateView):
    """Exhibitor management dashboard"""
    template_name = 'exhibitors/management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get exhibitors user can manage
        if self.request.user.is_staff:
            exhibitors = ExhibitorInfo.objects.all()
        else:
            exhibitors = ExhibitorInfo.objects.filter(
                staff__user=self.request.user
            ).distinct()
        
        exhibitors = exhibitors.select_related('event').prefetch_related(
            'staff', 'leads', 'contact_requests'
        ).annotate(
            lead_count=Count('leads'),
            contact_count=Count('contact_requests')
        )
        
        context.update({
            'exhibitors': exhibitors,
        })
        
        return context


class ExhibitorCreateView(LoginRequiredMixin, CreateView):
    """Create new exhibitor"""
    model = ExhibitorInfo
    form_class = ExhibitorForm
    template_name = 'exhibitors/form.html'
    success_url = reverse_lazy('exhibitors:management')
    
    def form_valid(self, form):
        messages.success(self.request, _('Exhibitor created successfully.'))
        return super().form_valid(form)


class ExhibitorEditView(LoginRequiredMixin, UpdateView):
    """Edit existing exhibitor"""
    model = ExhibitorInfo
    form_class = ExhibitorForm
    template_name = 'exhibitors/form.html'
    success_url = reverse_lazy('exhibitors:management')
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return ExhibitorInfo.objects.all()
        return ExhibitorInfo.objects.filter(
            staff__user=self.request.user,
            staff__can_edit_info=True
        )
    
    def form_valid(self, form):
        messages.success(self.request, _('Exhibitor updated successfully.'))
        return super().form_valid(form)


class ExhibitorDeleteView(LoginRequiredMixin, DeleteView):
    """Delete exhibitor"""
    model = ExhibitorInfo
    template_name = 'exhibitors/confirm_delete.html'
    success_url = reverse_lazy('exhibitors:management')
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return ExhibitorInfo.objects.all()
        return ExhibitorInfo.objects.filter(
            staff__user=self.request.user,
            staff__role='admin'
        )
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Exhibitor deleted successfully.'))
        return super().delete(request, *args, **kwargs)


class ExhibitorSearchView(View):
    """AJAX search for exhibitors"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        event_id = request.GET.get('event_id')
        
        exhibitors = ExhibitorInfo.objects.filter(is_active=True)
        
        if event_id:
            exhibitors = exhibitors.filter(event_id=event_id)
        
        if query:
            exhibitors = exhibitors.filter(
                Q(name__icontains=query) |
                Q(tagline__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct()
        
        exhibitors = exhibitors[:20]  # Limit results
        
        serializer = ExhibitorListSerializer(exhibitors, many=True)
        return JsonResponse({
            'exhibitors': serializer.data,
            'count': exhibitors.count()
        })


class ExhibitorContactView(View):
    """AJAX contact form submission"""
    
    def post(self, request, pk):
        exhibitor = get_object_or_404(ExhibitorInfo, pk=pk, is_active=True)
        
        if not exhibitor.contact_enabled:
            return JsonResponse({
                'success': False,
                'error': _('Contact form is disabled for this exhibitor.')
            }, status=400)
        
        serializer = ContactRequestCreateSerializer(data=request.POST)
        if serializer.is_valid():
            contact_request = serializer.save(exhibitor=exhibitor)
            
            # Create lead entry
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
            
            return JsonResponse({
                'success': True,
                'message': _('Your message has been sent successfully.')
            })
        
        return JsonResponse({
            'success': False,
            'errors': serializer.errors
        }, status=400)


class ExhibitorAnalyticsView(LoginRequiredMixin, View):
    """AJAX analytics data for exhibitor"""
    
    def get(self, request, pk):
        exhibitor = get_object_or_404(ExhibitorInfo, pk=pk)
        
        # Check permissions
        if not request.user.is_staff and not exhibitor.staff.filter(user=request.user).exists():
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Calculate analytics
        total_leads = exhibitor.leads.count()
        total_contact_requests = exhibitor.contact_requests.count()
        
        # Leads by type
        leads_by_type = dict(
            exhibitor.leads.values('scan_type').annotate(
                count=Count('id')
            ).values_list('scan_type', 'count')
        )
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_leads = exhibitor.leads.filter(scanned__gte=thirty_days_ago).count()
        recent_contacts = exhibitor.contact_requests.filter(
            created_at__gte=thirty_days_ago
        ).count()
        
        # Contact requests by status
        contact_requests_by_status = dict(
            exhibitor.contact_requests.values('status').annotate(
                count=Count('id')
            ).values_list('status', 'count')
        )
        
        return JsonResponse({
            'total_leads': total_leads,
            'total_contact_requests': total_contact_requests,
            'leads_by_type': leads_by_type,
            'contact_requests_by_status': contact_requests_by_status,
            'recent_leads': recent_leads,
            'recent_contacts': recent_contacts,
            'engagement_score': total_leads + (total_contact_requests * 2)
        })