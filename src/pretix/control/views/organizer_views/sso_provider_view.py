
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from pretix.base.models.customers import CustomerSSOClient, CustomerSSOProvider
from pretix.control.forms.organizer_forms import SSOClientForm, SSOProviderForm
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)
from pretix.multidomain.urlreverse import build_absolute_uri


class SSOProviderListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = CustomerSSOProvider
    template_name = 'pretixcontrol/organizers/sso_provider_list.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'providers'

    def get_queryset(self):
        return self.request.organizer.sso_providers.all()


class SSOProviderCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    model = CustomerSSOProvider
    template_name = 'pretixcontrol/organizers/sso_provider_detail.html'
    permission = 'can_change_organizer_settings'
    form_class = SSOProviderForm

    def get_object(self, queryset=None):
        return get_object_or_404(CustomerSSOProvider, organizer=self.request.organizer, pk=self.kwargs.get('provider'))

    def get_success_url(self):
        return reverse('control:organizer.ssoproviders', kwargs={
            'organizer': self.request.organizer.slug,
        })

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.organizer
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _('The provider has been created.'))
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        form.instance.log_action('pretix.ssoprovider.created', user=self.request.user, data={
            k: getattr(self.object, k, self.object.configuration.get(k)) for k in form.changed_data
        })
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class SSOProviderUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = CustomerSSOProvider
    template_name = 'pretixcontrol/organizers/sso_provider_detail.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'provider'
    form_class = SSOProviderForm

    def get_object(self, queryset=None):
        return get_object_or_404(CustomerSSOProvider, organizer=self.request.organizer, pk=self.kwargs.get('provider'))

    def get_success_url(self):
        return reverse('control:organizer.ssoproviders', kwargs={
            'organizer': self.request.organizer.slug,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['redirect_uri'] = build_absolute_uri(self.request.organizer, 'presale:organizer.customer.login.return',
                                                 kwargs={
                                                     'provider': self.object.pk
                                                 })
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.organizer
        return kwargs

    def form_valid(self, form):
        if form.has_changed():
            self.object.log_action('pretix.ssoprovider.changed', user=self.request.user, data={
                k: getattr(self.object, k, self.object.configuration.get(k)) for k in form.changed_data
            })
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class SSOProviderDeleteView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DeleteView):
    model = CustomerSSOProvider
    template_name = 'pretixcontrol/organizers/ssoprovider_remove.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'provider'

    def get_object(self, queryset=None):
        return get_object_or_404(CustomerSSOProvider, organizer=self.request.organizer, pk=self.kwargs.get('provider'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_allowed'] = self.object.allow_delete()
        return ctx

    def get_success_url(self):
        return reverse('control:organizer.ssoproviders', kwargs={
            'organizer': self.request.organizer.slug,
        })

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.object = self.get_object()
        if self.object.allow_delete():
            self.object.log_action('pretix.ssoprovider.deleted', user=self.request.user)
            self.object.delete()
            messages.success(request, _('The selected object has been deleted.'))
        return redirect(success_url)


class SSOClientListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = CustomerSSOClient
    template_name = 'pretixcontrol/organizers/ssoclients.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'clients'

    def get_queryset(self):
        return self.request.organizer.sso_clients.all()


class SSOClientCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    model = CustomerSSOClient
    template_name = 'pretixcontrol/organizers/ssoclient_edit.html'
    permission = 'can_change_organizer_settings'
    form_class = SSOClientForm

    def get_object(self, queryset=None):
        return get_object_or_404(CustomerSSOClient, organizer=self.request.organizer, pk=self.kwargs.get('client'))

    def get_success_url(self):
        return reverse('control:organizer.ssoclient.edit', kwargs={
            'organizer': self.request.organizer.slug,
            'client': self.object.pk
        })

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.organizer
        return kwargs

    def form_valid(self, form):
        secret = form.instance.set_client_secret()
        messages.success(
            self.request,
            _('The SSO client has been created. Please note down the following client secret, it will never be shown '
              'again: {secret}').format(secret=secret)
        )
        form.instance.organizer = self.request.organizer
        ret = super().form_valid(form)
        form.instance.log_action('pretix.ssoclient.created', user=self.request.user, data={
            k: getattr(self.object, k, form.cleaned_data.get(k)) for k in form.changed_data
        })
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class SSOClientUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = CustomerSSOClient
    template_name = 'pretixcontrol/organizers/ssoclient_edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'client'
    form_class = SSOClientForm

    def get_object(self, queryset=None):
        return get_object_or_404(CustomerSSOClient, organizer=self.request.organizer, pk=self.kwargs.get('client'))

    def get_success_url(self):
        return reverse('control:organizer.ssoclient.edit', kwargs={
            'organizer': self.request.organizer.slug,
            'client': self.object.pk
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.organizer
        return kwargs

    def form_valid(self, form):
        if form.has_changed():
            self.object.log_action('pretix.ssoclient.changed', user=self.request.user, data={
                k: getattr(self.object, k, form.cleaned_data.get(k)) for k in form.changed_data
            })
        if form.cleaned_data.get('regenerate_client_secret'):
            secret = form.instance.set_client_secret()
            messages.success(
                self.request,
                _('Your changes have been saved. Please note down the following client secret, it will never be shown '
                  'again: {secret}').format(secret=secret)
            )
        else:
            messages.success(
                self.request,
                _('Your changes have been saved.')
            )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class SSOClientDeleteView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DeleteView):
    model = CustomerSSOClient
    template_name = 'pretixcontrol/organizers/ssoclient_delete.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'client'

    def get_object(self, queryset=None):
        return get_object_or_404(CustomerSSOClient, organizer=self.request.organizer, pk=self.kwargs.get('client'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_allowed'] = self.object.allow_delete()
        return ctx

    def get_success_url(self):
        return reverse('control:organizer.ssoclients', kwargs={
            'organizer': self.request.organizer.slug,
        })

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.object = self.get_object()
        if self.object.allow_delete():
            self.object.log_action('pretix.ssoclient.deleted', user=self.request.user)
            self.object.delete()
            messages.success(request, _('The selected object has been deleted.'))
        return redirect(success_url)
