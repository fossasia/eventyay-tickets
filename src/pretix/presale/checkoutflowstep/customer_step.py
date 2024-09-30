from django.contrib import messages
from django.core.signing import BadSignature, loads
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from pretix.base.models import Customer
from pretix.helpers.http import redirect_to_url
from pretix.presale.forms.customer_forms import AuthenticationForm, RegistrationForm
from pretix.presale.utils import customer_login
from pretix.presale.views import CartMixin
from pretix.presale.views.questions import QuestionsViewMixin

from .template_flow_step import TemplateFlowStep


class CustomerStep(QuestionsViewMixin, CartMixin, TemplateFlowStep):
    priority = 45
    identifier = "customer"
    template_name = "pretixpresale/event/checkout_customer.html"
    label = pgettext_lazy('checkoutflow', 'Customer account')
    icon = 'user'

    def is_applicable(self, request):
        return request.organizer.settings.customer_accounts

    @cached_property
    def login_form(self):
        f = AuthenticationForm(
            data=(
                self.request.POST
                if self.request.method == "POST" and self.request.POST.get('customer_mode') == 'login'
                else None
            ),
            prefix='login',
            request=self.request.event,
        )
        for field in f.fields.values():
            field._show_required = field.required
            field.required = False
            field.widget.is_required = False
        return f

    @cached_property
    def signup_allowed(self):
        return self.request.event.settings.customer_accounts_native

    @cached_property
    def guest_allowed(self):
        if self.request.event.settings.ticket_buying_settings == False:
            return True
        return False

    @cached_property
    def register_form(self):
        f = RegistrationForm(
            data=(
                self.request.POST
                if self.request.method == "POST" and self.request.POST.get('customer_mode') == 'register'
                else None
            ),
            prefix='register',
            request=self.request,
        )
        for field in f.fields.values():
            field._show_required = field.required
            field.required = False
            field.widget.is_required = False
        return f

    def _handle_sso_login(self):
        value = self.request.POST['login-sso-data']
        try:
            data = loads(value, salt=f'customer_sso_popup_{self.request.organizer.pk}', max_age=120)
        except BadSignature:
            return False
        try:
            customer = self.request.organizer.customers.get(pk=data['customer'], provider__isnull=False)
        except Customer.DoesNotExist:
            return False
        self.cart_session['customer_mode'] = 'login'
        self.cart_session['customer'] = customer.pk
        self.cart_session['customer_cart_tied_to_login'] = True
        customer_login(self.request, customer)
        return True

    def post(self, request):
        self.request = request

        if request.POST.get("customer_mode") == 'login':
            if self.cart_session.get('customer'):
                return redirect_to_url(self.get_next_url(request))
            elif request.customer:
                self.cart_session['customer_mode'] = 'login'
                self.cart_session['customer'] = request.customer.pk
                self.cart_session['customer_cart_tied_to_login'] = True
                return redirect_to_url(self.get_next_url(request))
            elif self.request.POST.get("login-sso-data"):
                if not self._handle_sso_login():
                    messages.error(request, _('We failed to process your authentication request, please try again.'))
                    return self.render()
                return redirect_to_url(self.get_next_url(request))
            elif self.event.settings.customer_accounts_native and self.login_form.is_valid():
                customer_login(self.request, self.login_form.get_customer())
                self.cart_session['customer_mode'] = 'login'
                self.cart_session['customer'] = self.login_form.get_customer().pk
                self.cart_session['customer_cart_tied_to_login'] = True
                return redirect_to_url(self.get_next_url(request))
            else:
                return self.render()
        elif request.POST.get("customer_mode") == 'register' and self.signup_allowed:
            if self.register_form.is_valid():
                customer = self.register_form.create()
                self.cart_session['customer_mode'] = 'login'
                self.cart_session['customer'] = customer.pk
                self.cart_session['customer_cart_tied_to_login'] = False
                return redirect_to_url(self.get_next_url(request))
            else:
                return self.render()
        elif request.POST.get("customer_mode") == 'guest' and self.guest_allowed:
            self.cart_session['customer'] = None
            self.cart_session['customer_mode'] = 'guest'
            return redirect_to_url(self.get_next_url(request))
        else:
            messages.error(request, _('By continue, please log in or continue as guest.'))
            return self.render()

    def is_completed(self, request, warn=False):
        self.request = request
        if self.guest_allowed:
            return 'customer_mode' in self.cart_session
        else:
            return self.cart_session.get('customer_mode') == 'login'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cart'] = self.get_cart()
        ctx['cart_session'] = self.cart_session
        ctx['login_form'] = self.login_form
        ctx['register_form'] = self.register_form
        ctx['selected'] = self.request.POST.get(
            'customer_mode',
            self.cart_session.get('customer_mode', 'login' if self.request.customer else '')
        )
        ctx['guest_allowed'] = self.guest_allowed

        if 'customer' in self.cart_session:
            try:
                ctx['customer'] = self.request.organizer.customers.get(pk=self.cart_session.get('customer', -1))
            except Customer.DoesNotExist:
                self.cart_session['customer'] = None
                self.cart_session['customer_mode'] = None
        elif self.request.customer:
            ctx['customer'] = self.request.customer

        return ctx
