from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views.event import (
    EventSettingsFormView, EventSettingsViewMixin,
)
from pretix.helpers.models import modelcopy

from .forms import ExhibitorInfoForm
from .models import ExhibitorInfo, ExhibitorSettings


class SettingsView(EventPermissionRequiredMixin, ListView):
    model = ExhibitorInfo
    template_name = 'exhibitors/settings.html'
    context_object_name = 'exhibitors'
    permission = 'can_change_settings'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        settings, _ = ExhibitorSettings.objects.get_or_create(event=self.request.event)
        ctx['settings'] = settings
        ctx['default_fields'] = ['attendee_name', 'attendee_email']
        return ctx

    def post(self, request, *args, **kwargs):
        settings, _ = ExhibitorSettings.objects.get_or_create(event=self.request.event)
        
        # Define whitelist of supported field names
        supported_fields = ['attendee_name', 'attendee_email', 'company_name', 'badge_id', 'phone', 'address']
        
        # Get selected fields, excluding default fields
        allowed_fields = request.POST.getlist('exhibitors_access_voucher')
        # Validate allowed_fields against whitelist
        allowed_fields = [field for field in allowed_fields if field in supported_fields]
        
        # Update settings
        settings.allowed_fields = allowed_fields
        settings.exhibitors_access_mail_subject = request.POST.get('exhibitors_access_mail_subject', '')
        settings.exhibitors_access_mail_body = request.POST.get('exhibitors_access_mail_body', '')
        settings.save()
        
        messages.success(request, _('Settings have been saved.'))
        return redirect(request.path)


class ExhibitorListView(EventPermissionRequiredMixin, ListView):
    model = ExhibitorInfo
    permission = ('can_change_event_settings', 'can_view_orders')
    template_name = 'exhibitors/exhibitor_info.html'
    context_object_name = 'exhibitors'

    def get_success_url(self) -> str:
        return reverse('plugins:exhibitors:index', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorCreateView(EventPermissionRequiredMixin, CreateView):
    model = ExhibitorInfo
    form_class = ExhibitorInfoForm
    template_name = 'exhibitors/add.html'
    permission = 'can_change_event_settings'

    def form_valid(self, form):
        form.instance.event = self.request.event
        form.instance.lead_scanning_enabled = form.cleaned_data.get('lead_scanning_enabled', False)

        # Only generate booth_id if none was provided
        if not form.cleaned_data.get('booth_id'):
            form.instance.booth_id = generate_booth_id()

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        return context

    def get_success_url(self):
        return reverse('plugins:exhibitors:info', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorEditView(EventPermissionRequiredMixin, UpdateView):
    model = ExhibitorInfo
    form_class = ExhibitorInfoForm
    template_name = 'exhibitors/add.html'
    permission = 'can_change_event_settings'

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        initial['lead_scanning_enabled'] = obj.lead_scanning_enabled
        return initial

    def form_valid(self, form):
        exhibitor = form.save(commit=False)
        exhibitor.lead_scanning_enabled = form.cleaned_data.get('lead_scanning_enabled', False)
        
        # generate booth_id if none provided and there isn't an existing one
        if not form.cleaned_data.get('booth_id') and not exhibitor.booth_id:
            exhibitor.booth_id = generate_booth_id()
            
        exhibitor.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit'
        return context

    def get_success_url(self):
        return reverse('plugins:exhibitors:info', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorDeleteView(EventPermissionRequiredMixin, DeleteView):
    model = ExhibitorInfo
    template_name = 'exhibitors/delete.html'
    permission = ('can_change_event_settings',)

    def get_success_url(self) -> str:
        return reverse('plugins:exhibitors:info', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorCopyKeyView(EventPermissionRequiredMixin, View):
    permission = ('can_change_event_settings',)

    def get(self, request, *args, **kwargs):
        exhibitor = get_object_or_404(ExhibitorInfo, pk=kwargs['pk'])
        from django.utils.html import escape
        response = HttpResponse(escape(exhibitor.key))
        response['Content-Disposition'] = (
            'attachment; filename="password.txt"'
        )
        return response
