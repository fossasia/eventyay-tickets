import logging
import secrets

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DeleteView, FormView, TemplateView

from pretix.api.models import OAuthApplication
from pretix.base.models import LogEntry, OrderPayment, OrderRefund
from pretix.base.services.update_check import check_result_table, update_check
from pretix.base.settings import GlobalSettingsObject
from pretix.control.forms.global_settings import (
    GlobalSettingsForm, SSOConfigForm, UpdateSettingsForm,
)
from pretix.control.permissions import (
    AdministratorPermissionRequiredMixin, StaffMemberRequiredMixin,
)

logger = logging.getLogger(__name__)


class GlobalSettingsView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_settings.html'
    form_class = GlobalSettingsForm

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request, _('Your changes have not been saved, see below for errors.')
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('control:admin.global.settings')


class SSOView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_sso.html'
    form_class = SSOConfigForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        oauth_applications = OAuthApplication.objects.all()
        context['oauth_applications'] = oauth_applications
        return context

    def form_valid(self, form):
        url = form.cleaned_data['redirect_url']

        try:
            result = self.create_oauth_application(url)
        except (IntegrityError, ValidationError, ObjectDoesNotExist) as e:
            error_type = type(e).__name__
            logger.error('Error while creating OAuth2 application: %s - %s', error_type, e)
            return self.render_to_response({'error_message': f'{error_type}: {e}'})

        return self.render_to_response(self.get_context_data(form=form, result=result))

    def form_invalid(self, form):
        messages.error(
            self.request, _('Your changes have not been saved, see below for errors.')
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('control:admin.global.sso')

    def create_oauth_application(self, redirect_uris):
        application, created = OAuthApplication.objects.get_or_create(
            redirect_uris=redirect_uris,
            defaults={
                'name': "Talk SSO Client",
                'client_type': OAuthApplication.CLIENT_CONFIDENTIAL,
                'authorization_grant_type': OAuthApplication.GRANT_AUTHORIZATION_CODE,
                'user': None,
                'client_id': secrets.token_urlsafe(32),
                'client_secret': secrets.token_urlsafe(64),
                'hash_client_secret': False,
                'skip_authorization': True,
            },
        )

        return {
            "success_message": (
                "Successfully created OAuth2 Application"
                if created
                else "OAuth2 Application with this redirect URI already exists"
            ),
            "client_id": application.client_id,
            "client_secret": application.client_secret,
        }


class DeleteOAuthApplicationView(AdministratorPermissionRequiredMixin, DeleteView):
    model = OAuthApplication
    success_url = reverse_lazy('control:admin.global.sso')


class UpdateCheckView(StaffMemberRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_update.html'
    form_class = UpdateSettingsForm

    def post(self, request, *args, **kwargs):
        if 'trigger' in request.POST:
            update_check.apply()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request, _('Your changes have not been saved, see below for errors.')
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['gs'] = GlobalSettingsObject()
        ctx['gs'].settings.set('update_check_ack', True)
        ctx['tbl'] = check_result_table()
        return ctx

    def get_success_url(self):
        return reverse('control:admin.global.update')


class MessageView(TemplateView):
    template_name = 'pretixcontrol/global_message.html'


class LogDetailView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        le = get_object_or_404(LogEntry, pk=request.GET.get('pk'))
        return JsonResponse({'data': le.parsed_data})


class PaymentDetailView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        p = get_object_or_404(OrderPayment, pk=request.GET.get('pk'))
        return JsonResponse({'data': p.info_data})


class RefundDetailView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        p = get_object_or_404(OrderRefund, pk=request.GET.get('pk'))
        return JsonResponse({'data': p.info_data})


class SocialLoginView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/social_auth_settings.html'
    LOGIN_PROVIDERS = {'mediawiki': False, 'github': False, 'google': False}
    VALID_STATES = {'enable', 'disable'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gs = GlobalSettingsObject()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.gs.settings.get('login_providers', as_type=dict) is None:
            self.gs.settings.set('login_providers', self.LOGIN_PROVIDERS)
        context['login_providers'] = self.gs.settings.get('login_providers', as_type=dict)
        return context

    def post(self, request, *args, **kwargs):
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        for provider in self.LOGIN_PROVIDERS.keys():
            value = request.POST.get(f'{provider}_login', '').lower()
            if value not in self.VALID_STATES:
                continue
            elif value == "enable":
                login_providers[provider] = True
            elif value == "disable":
                login_providers[provider] = False
            self.gs.settings.set('login_providers', login_providers)
            break
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse('control:admin.global.social.auth.settings')
