from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from eventyay.base.models.devices import Gate
from eventyay.control.forms.organizer_forms import GateForm
from eventyay.control.permissions import OrganizerPermissionRequiredMixin
from eventyay.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)


class GateListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = Gate
    template_name = 'pretixcontrol/organizers/gates.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'gates'

    def get_queryset(self):
        return self.request.organizer.gates.all()


class GateCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    model = Gate
    template_name = 'pretixcontrol/organizers/gate_edit.html'
    permission = 'can_change_organizer_settings'
    form_class = GateForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(Gate, organizer=self.request.organizer, pk=self.kwargs.get('gate'))

    def get_success_url(self):
        return reverse(
            'control:organizer.gates',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        messages.success(self.request, _('The gate has been created.'))
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        form.instance.log_action(
            'pretix.gate.created',
            user=self.request.user,
            data={k: getattr(self.object, k) for k in form.changed_data},
        )
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class GateUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = Gate
    template_name = 'pretixcontrol/organizers/gate_edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'gate'
    form_class = GateForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(Gate, organizer=self.request.organizer, pk=self.kwargs.get('gate'))

    def get_success_url(self):
        return reverse(
            'control:organizer.gates',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        if form.has_changed():
            self.object.log_action(
                'pretix.gate.changed',
                user=self.request.user,
                data={k: getattr(self.object, k) for k in form.changed_data},
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class GateDeleteView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DeleteView):
    model = Gate
    template_name = 'pretixcontrol/organizers/gate_delete.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'gate'

    def get_object(self, queryset=None):
        return get_object_or_404(Gate, organizer=self.request.organizer, pk=self.kwargs.get('gate'))

    def get_success_url(self):
        return reverse(
            'control:organizer.gates',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    @transaction.atomic
    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object = self.get_object()
        self.object.log_action('pretix.gate.deleted', user=self.request.user)
        self.object.delete()
        messages.success(self.request, _('The selected gate has been deleted.'))
        return redirect(success_url)
