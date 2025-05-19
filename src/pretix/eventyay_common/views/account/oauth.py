import logging

from django import forms
from django.views.generic import ListView
from oauth2_provider.scopes import get_scopes_backend
from oauth2_provider.models import get_application_model
from oauth2_provider.views import (
    ApplicationDelete, ApplicationDetail, ApplicationList,
    ApplicationRegistration, ApplicationUpdate,
)

from pretix.api.models import (
    OAuthAccessToken, OAuthApplication, OAuthRefreshToken
)
from pretix.control.signals import oauth_application_registered

from .common import AccountMenuMixIn


logger = logging.getLogger(__name__)


class OAuthAuthorizedAppListView(AccountMenuMixIn, ListView):
    template_name = 'eventyay_common/account/authorized-apps.html'
    context_object_name = 'tokens'

    def get_queryset(self):
        return OAuthAccessToken.objects.filter(
            user=self.request.user
        ).select_related('application').prefetch_related('organizers')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_scopes = get_scopes_backend().get_all_scopes()
        for t in ctx['tokens']:
            t.scopes_descriptions = [all_scopes[scope] for scope in t.scopes]
        return ctx


class OAuthOwnAppListView(AccountMenuMixIn, ApplicationList):
    template_name = 'eventyay_common/account/own-apps.html'

    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class OAuthApplicationRegistrationView(AccountMenuMixIn, ApplicationRegistration):
    template_name = 'pretixcontrol/oauth/app_register.html'

    def get_form_class(self):
        return forms.modelform_factory(
            get_application_model(),
            fields=(
                "name", "redirect_uris"
            )
        )

    def form_valid(self, form):
        form.instance.client_type = 'confidential'
        form.instance.authorization_grant_type = 'authorization-code'
        oauth_application_registered.send(
            sender=self.request, user=self.request.user, application=form.instance
        )
        return super().form_valid(form)
