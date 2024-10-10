from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, View

from pretix.helpers.cookies import set_cookie_without_samesite
from pretix.helpers.jwt_generate import generate_customer_sso_token
from pretix.multidomain.middlewares import get_cookie_domain
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.forms.customer_forms import (
    AuthenticationForm, RegistrationForm,
)
from pretix.presale.utils import customer_login, customer_logout
from pretix.presale.views.customer import RedirectBackMixin


class LoginView(RedirectBackMixin, FormView):
    """
    Display the login form and handle the login action.
    """
    form_class = AuthenticationForm
    template_name = 'pretixpresale/organizers/customer_login.html'
    redirect_authenticated_user = True

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')
        if self.redirect_authenticated_user and self.request.customer:
            redirect_to = self.get_success_url()
            if redirect_to == self.request.path:
                raise ValueError(
                    "Redirection loop for authenticated user detected. Check that "
                    "your LOGIN_REDIRECT_URL doesn't point to a login page."
                )
            return HttpResponseRedirect(redirect_to)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            **kwargs,
            providers=self.request.organizer.sso_providers.all()
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_success_url(self):
        url = self.get_redirect_url()
        return url or eventreverse(self.request.organizer, 'presale:organizer.customer.profile', kwargs={})

    def form_valid(self, form):
        """Security check complete. Log the user in."""
        customer_login(self.request, form.get_customer())
        response = HttpResponseRedirect(self.get_success_url())
        response = set_cookie_after_logged_in(self.request, response)
        return response


class LogoutView(View):
    """
    A view that handles the logout process for a customer.

    Attributes:
        redirect_field_name (str): The name of the query parameter used for redirection after logout. Defaults to 'next'.
    """

    redirect_field_name = 'next'

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        """
        Dispatches the request to the appropriate handler. This method logs out the customer and redirects them.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponseRedirect: Redirects to the next page after logout.
        """
        customer_logout(request)
        next_page = self.get_next_page()
        return HttpResponseRedirect(next_page)

    def get_next_page(self):
        """
        Determines the next page to redirect to after logout.

        This method checks for a redirect URL in the POST or GET parameters.
        If a valid URL is found, it is used as the next page.
        Otherwise, the user is redirected to the default page.

        Returns:
            str: The URL of the next page to redirect to.
        """
        next_page = eventreverse(self.request.organizer, 'presale:organizer.index', kwargs={})

        if (self.redirect_field_name in self.request.POST or
                self.redirect_field_name in self.request.GET):
            next_page = self.request.POST.get(
                self.redirect_field_name,
                self.request.GET.get(self.redirect_field_name)
            )
            url_is_safe = url_has_allowed_host_and_scheme(
                url=next_page,
                allowed_hosts=None,
                require_https=self.request.is_secure(),
            )
            if not url_is_safe:
                next_page = self.request.path
        return next_page


class RegistrationView(RedirectBackMixin, FormView):
    form_class = RegistrationForm
    template_name = 'pretixpresale/organizers/customer_registration.html'
    redirect_authenticated_user = True

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        """
        Dispatches the request to the appropriate handler with additional checks and protections.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponseRedirect or HttpResponse: Redirects authenticated users to the success URL or
            proceeds with the normal dispatch process for other requests.

        Raises:
            Http404: If customer accounts or native customer accounts features are not enabled.
            ValueError: If a redirection loop is detected for authenticated users.
        """
        # Check if customer accounts are enabled
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')

        # Check if native customer accounts are enabled
        if not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')

        # Redirect authenticated users to the success URL
        if self.redirect_authenticated_user and self.request.customer:
            redirect_to = self.get_success_url()

            # Prevent redirection loop
            if redirect_to == self.request.path:
                raise ValueError(
                    "Redirection loop for authenticated user detected. Check that "
                    "your LOGIN_REDIRECT_URL doesn't point to a login page."
                )
            return HttpResponseRedirect(redirect_to)

        # Proceed with the normal dispatch process
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_success_url(self):
        url = self.get_redirect_url()
        return url or eventreverse(self.request.organizer, 'presale:organizer.customer.login', kwargs={})

    def form_valid(self, form):
        with transaction.atomic():
            form.create()
        messages.success(
            self.request,
            _('Your account has been created. Please follow the link in the email we sent you to activate your '
              'account and choose a password.')
        )
        return HttpResponseRedirect(self.get_success_url())


def set_cookie_after_logged_in(request, response):
    if response.status_code == 302 and request.customer:
        # Set JWT as a cookie in the response
        token = generate_customer_sso_token(request.customer)
        set_cookie_without_samesite(
            request, response,
            "customer_sso_token",
            token,
            max_age=settings.CSRF_COOKIE_AGE,
            domain=get_cookie_domain(request),
            path=settings.CSRF_COOKIE_PATH,
            secure=request.scheme == 'https',
            httponly=settings.CSRF_COOKIE_HTTPONLY
        )
    return response
