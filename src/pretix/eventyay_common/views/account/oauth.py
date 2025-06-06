import logging

from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, DetailView
from django.shortcuts import redirect
from oauth2_provider.scopes import get_scopes_backend
from oauth2_provider.models import get_application_model
from oauth2_provider.views import (
    ApplicationDelete,
    ApplicationDetail,
    ApplicationList,
    ApplicationRegistration,
    ApplicationUpdate,
)
from oauth2_provider.generators import generate_client_secret

from pretix.api.models import OAuthAccessToken, OAuthApplication, OAuthRefreshToken
from pretix.control.signals import oauth_application_registered

from .common import AccountMenuMixIn


logger = logging.getLogger(__name__)


class OAuthAuthorizedAppListView(AccountMenuMixIn, ListView):
    template_name = 'eventyay_common/account/authorized-apps.html'
    context_object_name = 'tokens'

    def get_queryset(self):
        return (
            OAuthAccessToken.objects.filter(user=self.request.user)
            .select_related('application')
            .prefetch_related('organizers')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_scopes = get_scopes_backend().get_all_scopes()
        for t in ctx['tokens']:
            t.scopes_descriptions = [all_scopes[scope] for scope in t.scopes]
        return ctx


class OAuthAuthorizedAppRevokeView(DetailView):
    template_name = 'eventyay_common/account/authorized-app-revoke.html'
    success_url = reverse_lazy('eventyay_common:account.oauth.authorized-apps')

    def get_queryset(self):
        return OAuthAccessToken.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['application'] = self.get_object().application
        return ctx

    def post(self, request, *args, **kwargs):
        o = self.get_object()
        for rt in OAuthRefreshToken.objects.filter(access_token=o):
            rt.revoke()
        o.delete()

        messages.success(request, _('Access for the selected application has been revoked.'))
        return redirect(self.success_url)


class OAuthOwnAppListView(AccountMenuMixIn, ApplicationList):
    template_name = 'eventyay_common/account/own-apps.html'

    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class OAuthApplicationRegistrationView(AccountMenuMixIn, ApplicationRegistration):
    template_name = 'eventyay_common/account/oauth-app-register.html'

    def get_form_class(self):
        return forms.modelform_factory(get_application_model(), fields=('name', 'redirect_uris'))

    def form_valid(self, form):
        form.instance.client_type = 'confidential'
        form.instance.authorization_grant_type = 'authorization-code'
        oauth_application_registered.send(sender=self.request, user=self.request.user, application=form.instance)
        return super().form_valid(form)


class ApplicationUpdateForm(forms.ModelForm):
    class Meta:
        model = OAuthApplication
        fields = ('name', 'client_id', 'client_secret', 'redirect_uris')

    def clean_client_id(self):
        return self.instance.client_id

    def clean_client_secret(self):
        return self.instance.client_secret

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client_id'].widget.attrs['readonly'] = True
        self.fields['client_secret'].widget.attrs['readonly'] = True


class OAuthApplicationUpdateView(AccountMenuMixIn, ApplicationUpdate):
    template_name = 'eventyay_common/account/oauth-app-update.html'

    def get_form_class(self):
        return ApplicationUpdateForm

    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class OAuthApplicationRollView(ApplicationDetail):
    template_name = 'eventyay_common/account/oauth-app-rollkeys.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.get_object()
        confirm_message = _('Are you sure you want to generate a new client secret for the application {code}?')
        ctx['confirm_message'] = confirm_message.format(code=f'<strong>{obj}</strong>')
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, _('A new client secret has been generated and is now effective.'))
        self.object.client_secret = generate_client_secret()
        self.object.save()
        return HttpResponseRedirect(self.object.get_absolute_url())

    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class OAuthApplicationDeleteView(ApplicationDelete):
    template_name = 'eventyay_common/account/oauth-app-delete.html'
    success_url = reverse_lazy('eventyay_common:account.oauth.own-apps')

    def get_queryset(self):
        return super().get_queryset().filter(active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.get_object()
        confirm_message = _('Are you sure you want to disable the application {code} permanently?')
        ctx['confirm_message'] = confirm_message.format(code=f'<strong>{obj}</strong>')
        return ctx

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.active = False
        self.object.save()
        return HttpResponseRedirect(self.success_url)
