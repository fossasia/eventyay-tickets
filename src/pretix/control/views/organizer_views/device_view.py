import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from pretix.base.models.devices import Device
from pretix.base.models.log import LogEntry
from pretix.control.forms.organizer_forms.device_form import DeviceForm
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)


class DeviceCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_edit.html'
    permission = 'can_change_organizer_settings'
    form_class = DeviceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_success_url(self):
        return reverse('control:organizer.device.connect', kwargs={'organizer': self.request.organizer.slug, 'device': self.object.pk})

    def form_valid(self, form):
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        form.instance.log_action(
            'pretix.device.created',
            user=self.request.user,
            data={k: getattr(self.object, k) if k != 'limit_events' else [e.id for e in getattr(self.object, k).all()] for k in form.changed_data},
        )
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class DeviceListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = Device
    template_name = 'pretixcontrol/organizers/devices.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'devices'

    def get_queryset(self):
        return self.request.organizer.devices.prefetch_related('limit_events').order_by('revoked', '-device_id')


class DeviceLogView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/organizers/device_logs.html'
    permission = 'can_change_organizer_settings'
    model = LogEntry
    context_object_name = 'logs'
    paginate_by = 20

    @cached_property
    def device(self):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['device'] = self.device
        return ctx

    def get_queryset(self):
        qs = (
            LogEntry.objects.filter(device_id=self.device)
            .select_related(
                'user',
                'content_type',
                'api_token',
                'oauth_application',
            )
            .prefetch_related('device', 'event')
            .order_by('-datetime')
        )
        return qs


class DeviceUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'device'
    form_class = DeviceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get_success_url(self):
        return reverse(
            'control:organizer.devices',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        if form.has_changed():
            self.object.log_action(
                'pretix.device.changed',
                user=self.request.user,
                data={k: getattr(self.object, k) if k != 'limit_events' else [e.id for e in getattr(self.object, k).all()] for k in form.changed_data},
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class DeviceConnectView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_connect.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'device'

    def get_object(self, queryset=None):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'ajax' in request.GET:
            return JsonResponse({'initialized': bool(self.object.initialized)})
        if self.object.initialized:
            messages.success(request, _('This device has been set up successfully.'))
            return redirect(
                reverse(
                    'control:organizer.devices',
                    kwargs={
                        'organizer': self.request.organizer.slug,
                    },
                )
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['qrdata'] = json.dumps(
            {
                'handshake_version': 1,
                'url': settings.SITE_URL,
                'token': self.object.initialization_token,
            }
        )
        return ctx


class DeviceRevokeView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    model = Device
    template_name = 'pretixcontrol/organizers/device_revoke.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'device'

    def get_object(self, queryset=None):
        return get_object_or_404(Device, organizer=self.request.organizer, pk=self.kwargs.get('device'))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.api_token:
            messages.success(request, _('This device currently does not have access.'))
            return redirect(
                reverse(
                    'control:organizer.devices',
                    kwargs={
                        'organizer': self.request.organizer.slug,
                    },
                )
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.revoked = True
        self.object.save()
        self.object.log_action('pretix.device.revoked', user=self.request.user)
        messages.success(request, _('Access for this device has been revoked.'))
        return redirect(
            reverse(
                'control:organizer.devices',
                kwargs={
                    'organizer': self.request.organizer.slug,
                },
            )
        )
