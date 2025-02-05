from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from pretix.base.models import CachedFile, LogEntry
from pretix.base.models.event import EventMetaProperty
from pretix.base.services.export import multiexport
from pretix.base.signals import register_multievent_data_exporters
from pretix.base.views.tasks import AsyncAction
from pretix.control.forms.orders import ExporterForm
from pretix.control.forms.organizer_forms import EventMetaPropertyForm
from pretix.control.logdisplay import OVERVIEW_BANLIST
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views import PaginationMixin
from pretix.control.views.organizer_views import OrganizerDetailViewMixin


class InviteForm(forms.Form):
    user = forms.EmailField(required=False, label=_('User'))


class TokenForm(forms.Form):
    name = forms.CharField(required=False, label=_('Token name'))


class ExportMixin:
    @cached_property
    def exporters(self):
        exporters = []
        events = self.request.user.get_events_with_permission('can_view_orders', request=self.request).filter(organizer=self.request.organizer)
        responses = register_multievent_data_exporters.send(self.request.organizer)
        id = self.request.GET.get('identifier') or self.request.POST.get('exporter')
        for ex in sorted([response(events) for r, response in responses if response], key=lambda ex: str(ex.verbose_name)):
            if id and ex.identifier != id:
                continue

            # Use form parse cycle to generate useful defaults
            test_form = ExporterForm(data=self.request.GET, prefix=ex.identifier)
            test_form.fields = ex.export_form_fields
            test_form.is_valid()
            initial = {k: v for k, v in test_form.cleaned_data.items() if ex.identifier + '-' + k in self.request.GET}

            ex.form = ExporterForm(data=(self.request.POST if self.request.method == 'POST' else None), prefix=ex.identifier, initial=initial)
            ex.form.fields = ex.export_form_fields
            ex.form.fields.update(
                [
                    (
                        'events',
                        forms.ModelMultipleChoiceField(
                            queryset=events,
                            initial=events,
                            widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
                            label=_('Events'),
                            required=True,
                        ),
                    ),
                ]
            )
            exporters.append(ex)
        return exporters

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['exporters'] = self.exporters
        return ctx


class ExportDoView(OrganizerPermissionRequiredMixin, ExportMixin, AsyncAction, TemplateView):
    known_errortypes = ['ExportError']
    task = multiexport
    template_name = 'pretixcontrol/organizers/export.html'

    def get_success_message(self, value):
        return None

    def get_success_url(self, value):
        return reverse('cachedfile.download', kwargs={'id': str(value)})

    def get_error_url(self):
        return reverse('control:organizer.export', kwargs={'organizer': self.request.organizer.slug})

    @cached_property
    def exporter(self):
        for ex in self.exporters:
            if ex.identifier == self.request.POST.get('exporter'):
                return ex

    def get(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return TemplateView.get(self, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.exporter:
            messages.error(self.request, _('The selected exporter was not found.'))
            return redirect('control:organizer.export', kwargs={'organizer': self.request.organizer.slug})

        if not self.exporter.form.is_valid():
            messages.error(self.request, _('There was a problem processing your input. See below for error details.'))
            return self.get(request, *args, **kwargs)

        cf = CachedFile(web_download=True, session_key=request.session.session_key)
        cf.date = now()
        cf.expires = now() + timedelta(hours=24)
        cf.save()
        return self.do(
            organizer=self.request.organizer.id,
            user=self.request.user.id,
            fileid=str(cf.id),
            provider=self.exporter.identifier,
            device=None,
            token=None,
            form_data=self.exporter.form.cleaned_data,
        )


class ExportView(OrganizerPermissionRequiredMixin, ExportMixin, TemplateView):
    template_name = 'pretixcontrol/organizers/export.html'


class EventMetaPropertyListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = EventMetaProperty
    template_name = 'pretixcontrol/organizers/properties.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'properties'

    def get_queryset(self):
        return self.request.organizer.meta_properties.all()


class EventMetaPropertyCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    model = EventMetaProperty
    template_name = 'pretixcontrol/organizers/property_edit.html'
    permission = 'can_change_organizer_settings'
    form_class = EventMetaPropertyForm

    def get_object(self, queryset=None):
        return get_object_or_404(EventMetaProperty, organizer=self.request.organizer, pk=self.kwargs.get('property'))

    def get_success_url(self):
        return reverse(
            'control:organizer.properties',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        messages.success(self.request, _('The property has been created.'))
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        form.instance.log_action('pretix.property.created', user=self.request.user, data={k: getattr(self.object, k) for k in form.changed_data})
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class EventMetaPropertyUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = EventMetaProperty
    template_name = 'pretixcontrol/organizers/property_edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'property'
    form_class = EventMetaPropertyForm

    def get_object(self, queryset=None):
        return get_object_or_404(EventMetaProperty, organizer=self.request.organizer, pk=self.kwargs.get('property'))

    def get_success_url(self):
        return reverse(
            'control:organizer.properties',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        if form.has_changed():
            self.object.log_action('pretix.property.changed', user=self.request.user, data={k: getattr(self.object, k) for k in form.changed_data})
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class EventMetaPropertyDeleteView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DeleteView):
    model = EventMetaProperty
    template_name = 'pretixcontrol/organizers/property_delete.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'property'

    def get_object(self, queryset=None):
        return get_object_or_404(EventMetaProperty, organizer=self.request.organizer, pk=self.kwargs.get('property'))

    def get_success_url(self):
        return reverse(
            'control:organizer.properties',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    @transaction.atomic
    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object = self.get_object()
        self.object.log_action('pretix.property.deleted', user=self.request.user)
        self.object.delete()
        messages.success(self.request, _('The selected property has been deleted.'))
        return redirect(success_url)


class LogView(OrganizerPermissionRequiredMixin, PaginationMixin, ListView):
    template_name = 'pretixcontrol/organizers/logs.html'
    permission = 'can_change_organizer_settings'
    model = LogEntry
    context_object_name = 'logs'

    def get_queryset(self):
        qs = self.request.organizer.all_logentries().select_related('user', 'content_type', 'api_token', 'oauth_application', 'device').order_by('-datetime')
        qs = qs.exclude(action_type__in=OVERVIEW_BANLIST)
        if self.request.GET.get('user'):
            qs = qs.filter(user_id=self.request.GET.get('user'))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        return ctx
