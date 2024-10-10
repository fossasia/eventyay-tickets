from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView

from pretix.base.models import Customer
from pretix.base.services.mail import mail
from pretix.multidomain.urlreverse import build_absolute_uri, eventreverse
from pretix.presale.forms.customer import TokenGenerator
from pretix.presale.forms.customer_forms import (
    ChangePasswordForm, ResetPasswordForm, SetPasswordForm,
)
from pretix.presale.utils import update_customer_session_auth_hash
from pretix.presale.views.customer import CustomerRequiredMixin


class SetPasswordView(FormView):
    form_class = SetPasswordForm
    template_name = 'pretixpresale/organizers/customer_setpassword.html'

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')
        if not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        try:
            self.customer = request.organizer.customers.get(identifier=self.request.GET.get('id'), provider__isnull=True)
        except Customer.DoesNotExist:
            messages.error(request, _('You clicked an invalid link.'))
            return HttpResponseRedirect(self.get_success_url())
        if not TokenGenerator().check_token(self.customer, self.request.GET.get('token', '')):
            messages.error(request, _('You clicked an invalid link.'))
            return HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['customer'] = self.customer
        return kwargs

    def get_success_url(self):
        return eventreverse(self.request.organizer, 'presale:organizer.customer.login', kwargs={})

    def form_valid(self, form):
        with transaction.atomic():
            self.customer.set_password(form.cleaned_data['password'])
            self.customer.is_verified = True
            self.customer.save()
            self.customer.log_action('pretix.customer.password.set', {})
        messages.success(
            self.request,
            _('Your new password has been set! You can now use it to log in.'),
        )
        return HttpResponseRedirect(self.get_success_url())


class ResetPasswordView(FormView):
    form_class = ResetPasswordForm
    template_name = 'pretixpresale/organizers/customer_resetpw.html'

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')
        if not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return eventreverse(self.request.organizer, 'presale:organizer.customer.login', kwargs={})

    def form_valid(self, form):
        customer = form.customer
        customer.log_action('pretix.customer.password.resetrequested', {})
        ctx = customer.get_email_context()
        token = TokenGenerator().make_token(customer)
        ctx['url'] = build_absolute_uri(self.request.organizer,
                                        'presale:organizer.customer.password.recover') + '?id=' + customer.identifier + '&token=' + token
        mail(
            customer.email,
            _('Set a new password for your account at {organizer}').format(organizer=self.request.organizer.name),
            self.request.organizer.settings.mail_text_customer_reset,
            ctx,
            locale=customer.locale,
            customer=customer,
            organizer=self.request.organizer,
        )
        messages.success(
            self.request,
            _('We\'ve sent you an email with further instructions on resetting your password.')
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class ChangePasswordView(CustomerRequiredMixin, FormView):
    template_name = 'pretixpresale/organizers/customer_password.html'
    form_class = ChangePasswordForm

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')
        if self.request.customer.provider_id:
            raise Http404('Feature not enabled')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return eventreverse(self.request.organizer, 'presale:organizer.customer.profile', kwargs={})

    @transaction.atomic()
    def form_valid(self, form):
        customer = form.customer
        customer.log_action('pretix.customer.password.set', {})
        customer.set_password(form.cleaned_data['password'])
        customer.save()
        messages.success(self.request, _('Your changes have been saved.'))
        update_customer_session_auth_hash(self.request, customer)
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['customer'] = self.request.customer
        return kwargs
