import logging
import secrets

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, TemplateView, DeleteView
from django.db import IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from pretix.base.models import LogEntry, OrderPayment, OrderRefund
from pretix.api.models import OAuthApplication
from pretix.base.services.update_check import check_result_table, update_check
from pretix.base.settings import GlobalSettingsObject
from pretix.control.forms.global_settings import (
    GlobalSettingsForm, UpdateSettingsForm, SSOConfigForm
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
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
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

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        return self.form_valid(form) if form.is_valid() else self.form_invalid(form)

    def form_valid(self, form):
        url = form.cleaned_data['redirect_url']

        try:
            result = self.create_oauth_application(url)
        except IntegrityError as e:
            logger.error("Error while creating OAuth2 application: %s", e)
            return {"error_message": f"Database integrity error: {str(e)}"}
        except ValidationError as e:
            logger.error("Error while creating OAuth2 application: %s", e)
            return {"error_message": f"Validation error: {e.message_dict}"}
        except ObjectDoesNotExist:
            logger.error("Error while creating OAuth2 application: %s", e)
            return {"error_message": "The object you are trying to access does not exist."}
        except ValueError as e:
            logger.error("Error while creating OAuth2 application: %s", e)
            return {"error_message": f"Value error: {str(e)}"}
        except Exception as e:
            logger.error("Error while creating OAuth2 application: %s", e)
            return {"error_message": f"An unexpected error occurred: {str(e)}"}

        return self.render_to_response(self.get_context_data(form=form, result=result))

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('control:admin.global.sso')

    def create_oauth_application(self, redirect_uris):
        # Check if the application already exists based on redirect_uri
        if OAuthApplication.objects.filter(redirect_uris=redirect_uris).exists():
            application = OAuthApplication.objects.filter(redirect_uris=redirect_uris).first()
            return {
                "success_message": "OAuth2 Application with this redirect URI already exists",
                "client_id": application.client_id,
                "client_secret": application.client_secret
            }
        else:
            # Create the OAuth2 Application
            application = OAuthApplication(
                name="Talk SSO Client",
                client_type=OAuthApplication.CLIENT_CONFIDENTIAL,
                authorization_grant_type=OAuthApplication.GRANT_AUTHORIZATION_CODE,
                redirect_uris=redirect_uris,
                user=None,  # Set a specific user if you want this to be user-specific, else keep it None
                client_id=secrets.token_urlsafe(32),
                client_secret=secrets.token_urlsafe(64),
                hash_client_secret=False,
                skip_authorization=True,
            )
            application.save()

        return {
            "success_message": "Successfully created OAuth2 Application",
            "client_id": application.client_id,
            "client_secret": application.client_secret
            }


class DeleteOAuthApplicationView(DeleteView):
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
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
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
