from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView

from pretix.api.models import WebHook
from pretix.control.forms.organizer_forms import WebHookForm
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)
from pretix.helpers.dicts import merge_dicts


class WebHookListView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView
):
    model = WebHook
    template_name = 'pretixcontrol/organizers/webhooks.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'webhooks'

    def get_queryset(self):
        return self.request.organizer.webhooks.prefetch_related('limit_events')


class WebHookCreateView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView
):
    model = WebHook
    template_name = 'pretixcontrol/organizers/webhook_edit.html'
    permission = 'can_change_organizer_settings'
    form_class = WebHookForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_success_url(self):
        return reverse(
            'control:organizer.webhooks',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        self.request.organizer.log_action(
            'pretix.webhook.created',
            user=self.request.user,
            data=merge_dicts(
                {
                    k: form.cleaned_data[k]
                    if k != 'limit_events'
                    else [e.id for e in getattr(self.object, k).all()]
                    for k in form.changed_data
                },
                {'id': form.instance.pk},
            ),
        )
        new_listeners = set(form.cleaned_data['events'])
        for l in new_listeners:
            self.object.listeners.create(action_type=l)
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class WebHookUpdateView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView
):
    model = WebHook
    template_name = 'pretixcontrol/organizers/webhook_edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'webhook'
    form_class = WebHookForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(
            WebHook, organizer=self.request.organizer, pk=self.kwargs.get('webhook')
        )

    def get_success_url(self):
        return reverse(
            'control:organizer.webhooks',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def form_valid(self, form):
        if form.has_changed():
            self.request.organizer.log_action(
                'pretix.webhook.changed',
                user=self.request.user,
                data=merge_dicts(
                    {
                        k: form.cleaned_data[k]
                        if k != 'limit_events'
                        else [e.id for e in getattr(self.object, k).all()]
                        for k in form.changed_data
                    },
                    {'id': form.instance.pk},
                ),
            )

        current_listeners = set(
            self.object.listeners.values_list('action_type', flat=True)
        )
        new_listeners = set(form.cleaned_data['events'])
        for l in current_listeners - new_listeners:
            self.object.listeners.filter(action_type=l).delete()
        for l in new_listeners - current_listeners:
            self.object.listeners.create(action_type=l)

        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class WebHookLogsView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView
):
    model = WebHook
    template_name = 'pretixcontrol/organizers/webhook_logs.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'calls'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['webhook'] = self.webhook
        return ctx

    @cached_property
    def webhook(self):
        return get_object_or_404(
            WebHook, organizer=self.request.organizer, pk=self.kwargs.get('webhook')
        )

    def get_queryset(self):
        return self.webhook.calls.order_by('-datetime')
