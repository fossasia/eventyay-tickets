from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext, gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from pretix.helpers.models import modelcopy

from .forms import ExhibitorInfoForm, ExhibitorSettingForm
from .models import ExhibitorInfo


class SettingsView(EventPermissionRequiredMixin, ListView):
    model = ExhibitorInfo
    template_name = 'exhibitors/settings.html'
    context_object_name = 'exhibitors'
    permission = 'can_change_settings'

    def get_queryset(self):
        return ExhibitorInfo.objects.filter(event=self.request.event)

    def post(self, request, *args, **kwargs):
        exhibitor_id = request.POST.get('exhibitor_id')
        exhibitor = get_object_or_404(
            ExhibitorInfo, id=exhibitor_id, event=request.event
        )
        lead_scanning_enabled = request.POST.get('lead_scanning_enabled') == 'true'
        exhibitor.lead_scanning_enabled = lead_scanning_enabled
        exhibitor.save()
        return JsonResponse({
            'success': True,
            'status': 'enabled' if lead_scanning_enabled else 'disabled'
        })


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
        form.instance.lead_scanning_enabled = (
            self.request.POST.get('lead_scanning_enabled') == 'on'
        )
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

    def form_valid(self, form):
        form.instance.lead_scanning_enabled = (
            self.request.POST.get('lead_scanning_enabled') == 'on'
        )
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
        response = HttpResponse(exhibitor.key)
        response['Content-Disposition'] = (
            'attachment; filename="password.txt"'
        )
        return response
