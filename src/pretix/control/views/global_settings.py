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
from pretix.common.enums import ValidStates
from pretix.control.forms.global_settings import (
    GlobalSettingsForm,
    SSOConfigForm,
    UpdateSettingsForm,
)
from pretix.control.permissions import (
    AdministratorPermissionRequiredMixin,
    StaffMemberRequiredMixin,
)

logger = logging.getLogger(__name__)


class GlobalSettingsView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/global_settings.html'
    form_class = GlobalSettingsForm
    active_tab = 'basics'  # Default active tab

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['active_tab'] = self.active_tab
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_tab'] = self.active_tab
        return ctx

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
        return reverse('control:admin.global.settings.' + self.active_tab)


class GlobalSettingsLocalizationView(GlobalSettingsView):
    active_tab = 'localization'


class GlobalSettingsEmailView(GlobalSettingsView):
    active_tab = 'email'


class GlobalSettingsPaymentGatewaysView(GlobalSettingsView):
    active_tab = 'payment_gateways'


class GlobalSettingsMapsView(GlobalSettingsView):
    active_tab = 'maps'


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
            logger.error(
                'Error while creating OAuth2 application: %s - %s', error_type, e
            )
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
                'name': 'Talk SSO Client',
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
            'success_message': (
                'Successfully created OAuth2 Application'
                if created
                else 'OAuth2 Application with this redirect URI already exists'
            ),
            'client_id': application.client_id,
            'client_secret': application.client_secret,
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


class ToggleBillingValidationView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/toggle_billing_validation.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gs = GlobalSettingsObject()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.gs.settings.get('billing_validation') is None:
            self.gs.settings.set('billing_validation', True)
        context['billing_validation'] = self.gs.settings.get('billing_validation')
        return context

    def post(self, request, *args, **kwargs):
        value = request.POST.get('billing_validation', '').lower()

        if value == ValidStates.DISABLED:
            billing_validation = False
        elif value == ValidStates.ENABLED:
            billing_validation = True
        else:
            logger.error('Invalid value for billing validation: %s', value)
            messages.error(request, _('Invalid value for billing validation!'))
            return redirect(self.get_success_url())

        self.gs.settings.set('billing_validation', billing_validation)
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse('control:admin.toggle.billing.validation')
