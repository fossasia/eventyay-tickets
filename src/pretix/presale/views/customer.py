import hashlib
from importlib import import_module
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, dumps, loads
from django.db import IntegrityError, transaction
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, ListView, View

from pretix.base.customersso.open_id_connect import (
    get_authorize_url, retrieve_user_profile,
)
from pretix.base.models import Customer, Order, OrderPosition
from pretix.base.services.mail import mail
from pretix.base.settings import PERSON_NAME_SCHEMES
from pretix.multidomain.models import KnownDomain
from pretix.multidomain.urlreverse import build_absolute_uri, eventreverse
from pretix.presale.forms.customer_forms import (
    AuthenticationForm, ChangeInfoForm,
)
from pretix.presale.utils import (
    customer_login, update_customer_session_auth_hash,
)

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


class RedirectBackMixin:
    redirect_field_name = 'next'

    def get_redirect_url(self, redirect_to=None):
        """
        Returns the user-originating redirect URL if it's safe.

        Args:
            redirect_to (str, optional): The URL to redirect to. If not provided,
                                         it checks POST and GET parameters.

        Returns:
            str: The safe redirect URL or an empty string if the URL is not safe.
        """
        redirect_to = redirect_to or self.request.POST.get(
            self.redirect_field_name,
            self.request.GET.get(self.redirect_field_name, '')
        )
        url_is_safe = url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts=None,
            require_https=self.request.is_secure(),
        )
        return redirect_to if url_is_safe else ''


class CustomerRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')
        if not getattr(request, 'customer', None):
            return redirect(
                eventreverse(self.request.organizer, 'presale:organizer.customer.login', kwargs={}) +
                '?next=' + quote(self.request.path_info + '?' + self.request.GET.urlencode())
            )
        return super().dispatch(request, *args, **kwargs)


class ProfileView(CustomerRequiredMixin, ListView):
    template_name = 'pretixpresale/organizers/customer_profile.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = Order.objects.filter(
            Q(customer=self.request.customer)
            | Q(email__iexact=self.request.customer.email)
        ).select_related('event').order_by('-datetime')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['customer'] = self.request.customer
        ctx['is_paginated'] = True

        s = OrderPosition.objects.filter(
            order=OuterRef('pk')
        ).order_by().values('order').annotate(k=Count('id')).values('k')
        annotated = {
            o['pk']: o
            for o in
            Order.annotate_overpayments(Order.objects, sums=True).filter(
                pk__in=[o.pk for o in ctx['orders']]
            ).annotate(
                pcnt=Subquery(s, output_field=IntegerField()),
            ).values(
                'pk', 'pcnt',
            )
        }

        for o in ctx['orders']:
            if o.pk not in annotated:
                continue
            o.count_positions = annotated.get(o.pk)['pcnt']
        return ctx


class ChangeInformationView(CustomerRequiredMixin, FormView):
    template_name = 'pretixpresale/organizers/customer_info.html'
    form_class = ChangeInfoForm

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')
        if self.request.customer:
            self.initial_email = self.request.customer.email
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return eventreverse(self.request.organizer, 'presale:organizer.customer.profile', kwargs={})

    def form_valid(self, form):
        if form.cleaned_data['email'] != self.initial_email and not self.request.customer.provider:
            new_email = form.cleaned_data['email']
            form.cleaned_data['email'] = form.instance.email = self.initial_email
            ctx = form.instance.get_email_context()
            ctx['url'] = build_absolute_uri(
                self.request.organizer,
                'presale:organizer.customer.change.confirm'
            ) + '?token=' + dumps({
                'customer': form.instance.pk,
                'email': new_email
            }, salt='pretix.presale.views.customer.ChangeInformationView')
            mail(
                new_email,
                _('Confirm email address for your account at {organizer}').format(
                    organizer=self.request.organizer.name),
                self.request.organizer.settings.mail_text_customer_email_change,
                ctx,
                locale=form.instance.locale,
                customer=form.instance,
                organizer=self.request.organizer,
            )
            messages.success(self.request,
                             _('Your changes have been saved. We\'ve sent you an email with a link to update your '
                               'email address. The email address of your account will be changed as soon as you '
                               'click that link.'))
        else:
            messages.success(self.request, _('Your changes have been saved.'))

        with transaction.atomic():
            form.save()
            d = dict(form.cleaned_data)
            del d['email']
            self.request.customer.log_action('eventyay.customer.changed', d)

        update_customer_session_auth_hash(self.request, form.instance)
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['instance'] = self.request.customer
        return kwargs


class ConfirmChangeView(View):
    template_name = 'pretixpresale/organizers/customer_info.html'

    def get(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')

        try:
            data = loads(request.GET.get('token', ''), salt='pretix.presale.views.customer.ChangeInformationView',
                         max_age=3600 * 24)
        except BadSignature:
            messages.error(request, _('You clicked an invalid link.'))
            return HttpResponseRedirect(self.get_success_url())

        try:
            customer = request.organizer.customers.get(pk=data.get('customer'), provider__isnull=True)
        except Customer.DoesNotExist:
            messages.error(request, _('You clicked an invalid link.'))
            return HttpResponseRedirect(self.get_success_url())

        with transaction.atomic():
            customer.email = data['email']
            customer.save()
            customer.log_action('eventyay.customer.changed', {
                'email': data['email']
            })

        messages.success(request, _('Your email address has been updated.'))

        if customer == request.customer:
            update_customer_session_auth_hash(self.request, customer)

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return eventreverse(self.request.organizer, 'presale:organizer.customer.profile', kwargs={})


class SSOLoginView(RedirectBackMixin, View):
    """
    Logging with an SSO provider.
    """
    form_class = AuthenticationForm
    redirect_authenticated_user = True

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        self.check_customer_accounts_enabled()
        if self.redirect_authenticated_user and self.request.customer:
            self.redirect_authenticated_user_to_success_url()
        return super().dispatch(request, *args, **kwargs)

    def check_customer_accounts_enabled(self):
        if not self.request.organizer.settings.customer_accounts:
            raise Http404('Feature not enabled')

    def redirect_authenticated_user_to_success_url(self):
        redirect_to = self.get_success_url()
        if redirect_to == self.request.path:
            raise ValueError(
                "Redirection loop detected for authenticated user. Ensure that "
                "your LOGIN_REDIRECT_URL does not point to a login page."
            )
        return HttpResponseRedirect(redirect_to)

    @cached_property
    def provider(self):
        return get_object_or_404(self.request.organizer.sso_providers.filter(is_active=True),
                                 pk=self.kwargs['provider'])

    def get(self, request, *args, **kwargs):
        next_url = self.get_next_url()
        popup_origin = self.get_popup_origin()

        nonce = self.generate_nonce()
        self.store_in_session(nonce, popup_origin)

        redirect_uri = self.build_redirect_uri()

        if self.provider.method == "oidc":
            return self.redirect_to_oidc_authorize_url(nonce, next_url, redirect_uri)
        else:
            return self.handle_unknown_sso_method()

    def get_next_url(self):
        return self.request.GET.get('next') or ''

    def get_popup_origin(self):
        popup_origin = self.request.GET.get('popup_origin', '')
        if popup_origin:
            popup_origin_parsed = urlparse(popup_origin)
            untrusted = (
                popup_origin_parsed.hostname != urlparse(settings.SITE_URL).hostname and
                not KnownDomain.objects.filter(domainname=popup_origin_parsed.hostname,
                                               organizer=self.request.organizer.pk).exists()
            )
            if untrusted:
                popup_origin = None
        return popup_origin

    def generate_nonce(self):
        return get_random_string(32)

    def store_in_session(self, nonce, popup_origin):
        self.request.session[f'eventyay_customer_auth_{self.provider.pk}_nonce'] = nonce
        self.request.session[f'eventyay_customer_auth_{self.provider.pk}_popup_origin'] = popup_origin
        self.request.session[
            f'eventyay_customer_auth_{self.provider.pk}_cross_domain_requested'] = self.request.GET.get(
            "request_cross_domain_customer_auth") == "true"

    def build_redirect_uri(self):
        return build_absolute_uri(self.request.organizer, 'presale:organizer.customer.login.return', kwargs={
            'provider': self.provider.pk
        })

    def redirect_to_oidc_authorize_url(self, nonce, next_url, redirect_uri):
        return redirect(get_authorize_url(self.provider, f'{nonce}#{next_url}', redirect_uri))

    def handle_unknown_sso_method(self):
        raise Http404("Unknown SSO method.")

    def get_success_url(self):
        url = self.get_redirect_url()

        if not url:
            return eventreverse(self.request.organizer, 'presale:organizer.customer.profile', kwargs={})
        return url


class SSOLoginReturnView(RedirectBackMixin, View):
    """
    Start logging in with a SSO provider.
    """
    form_class = AuthenticationForm
    redirect_authenticated_user = True

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        """
        This method is the first point of entry for any request in Django. It checks if customer accounts are enabled
        and if the user is already authenticated. If the user is authenticated, it redirects them to a success URL.
        If the success URL is the same as the current path, it raises a ValueError to prevent a redirection loop.
        If the user is not authenticated, it proceeds with the normal dispatch process. After the dispatch,
        it clears specific session variables.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: The HTTP response.
        """
        # Check if customer accounts are enabled
        if not request.organizer.settings.customer_accounts:
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
        response = super().dispatch(request, *args, **kwargs)

        # Clear specific session variables
        session_keys = [
            f'eventyay_customer_auth_{self.provider.pk}_nonce',
            f'eventyay_customer_auth_{self.provider.pk}_popup_origin',
            f'eventyay_customer_auth_{self.provider.pk}_cross_domain_requested'
        ]
        for key in session_keys:
            request.session.pop(key, None)

        return response

    @cached_property
    def provider(self):
        return get_object_or_404(self.request.organizer.sso_providers.filter(is_active=True),
                                 pk=self.kwargs['provider'])

    def get(self, request, *args, **kwargs):
        popup_origin = None

        if request.session.get(f'eventyay_customer_auth_{self.provider.pk}_popup_origin'):
            popup_origin = request.session[f'eventyay_customer_auth_{self.provider.pk}_popup_origin']

        if self.provider.method == "oidc":
            if not request.GET.get('state'):
                return self._fail(
                    _('Login failed. Error message: "{error}".').format(
                        error='issing state parameters',
                    ),
                    popup_origin,
                )

            nonce, redirect_to = request.GET['state'].split('#')

            if nonce != request.session.get(f'eventyay_customer_auth_{self.provider.pk}_nonce'):
                return self._fail(
                    _('Login failed. Error message: "{error}".').format(
                        error='nonce is invalid',
                    ),
                    popup_origin,
                )
            redirect_uri = build_absolute_uri(
                self.request.organizer, 'presale:organizer.customer.login.return',
                kwargs={
                    'provider': self.provider.pk
                }
            )
            try:
                profile = retrieve_user_profile(
                    self.provider,
                    request.GET.get('code'),
                    redirect_uri,
                )
            except ValidationError as e:
                for msg in e:
                    return self._fail(msg, popup_origin)
        else:
            raise Http404("SSO method not supported.")

        identifier = hashlib.sha256(
            profile['uid'].encode() + b'@' + str(self.provider.pk).encode()
        ).hexdigest().upper()[:settings.ENTROPY['customer_identifier']]
        if "1" not in identifier and "0" not in identifier:
            identifier = identifier[:4] + "1" + identifier[4:-1]

        try:
            customer = self.request.organizer.customers.get(
                provider=self.provider,
                identifier=identifier,
            )
        except Customer.MultipleObjectsReturned:
            return self._fail(
                _('Login failed. Error message: "{error}".').format(
                    error='duplicated identifier',
                ),
                popup_origin,
            )
        except Customer.DoesNotExist:
            name_scheme = self.request.organizer.settings.name_scheme
            name_parts = {
                '_scheme': name_scheme,
            }
            scheme = PERSON_NAME_SCHEMES.get(name_scheme)
            for fname, label, size in scheme['fields']:
                if fname in profile:
                    name_parts[fname] = profile[fname]
            if len(name_parts) == 1 and profile.get('name'):
                name_parts = {'_legacy': profile['name']}
            customer = Customer(
                organizer=self.request.organizer,
                identifier=identifier,
                external_identifier=profile['uid'],
                provider=self.provider,
                email=profile['email'],
                name_parts=name_parts,
                is_active=True,
                is_verified=True,
                locale=request.LANGUAGE_CODE,
            )
            try:
                customer.save(force_insert=True)
            except IntegrityError:
                try:
                    customer = self.request.organizer.customers.get(
                        provider=self.provider,
                        identifier=identifier,
                    )
                except Customer.DoesNotExist:
                    return self._fail(
                        _('We were unable to use your login since the email address {email} is already used for a '
                          'different account in this system.').format(email=profile['email']),
                        popup_origin,
                    )
        else:
            if customer.is_active and customer.email != profile['email']:
                customer.email = profile['email']
                try:
                    customer.save(update_fields=['email'])
                except IntegrityError:
                    return self._fail(
                        _('We were unable to use your login since the email address {email} is already used for a '
                          'different account in this system.').format(email=profile['email']),
                        popup_origin,
                    )
                customer.log_action('eventyay.customer.changed', {
                    'email': profile['email'],
                    '_source': 'provider'
                })

        if customer.external_identifier != profile['uid']:
            return self._fail(
                _('Login failed. Error message: "{error}".').format(
                    error='duplicated identifier',
                ),
                popup_origin,
            )

        if not customer.is_active:
            self._fail(
                AuthenticationForm.error_messages['inactive'],
                popup_origin,
            )

        if not customer.is_verified:
            return self._fail(
                AuthenticationForm.error_messages['unverified'],
                popup_origin
            )

        if popup_origin:
            return render(self.request, 'pretixpresale/popup-message.html', {
                'message': {
                    '__process': 'customer_sso_popup',
                    'status': 'ok',
                    'value': dumps({
                        'customer': customer.pk,
                    }, salt=f'customer_sso_popup_{self.request.organizer.pk}')
                },
                'origin': popup_origin,
            })
        else:
            customer_login(self.request, customer)
            return redirect(self.get_success_url(redirect_to))

    def _fail(self, message, popup_origin):
        if not popup_origin:
            messages.error(
                self.request,
                message,
            )
            return redirect(eventreverse(self.request.organizer, 'presale:organizer.customer.login', kwargs={}))
        else:
            return render(self.request, 'pretixpresale/popup-message.html', {
                'message': {
                    '__process': 'customer_sso_popup',
                    'status': 'error',
                    'value': str(message)
                },
                'origin': popup_origin,
            })

    def get_success_url(self, redirect_to=None):
        """
        Generate the URL to which the user will be redirected after a successful login.

        If a redirect URL is provided, it is used as the success URL. If the session indicates a cross-domain customer
        authentication request, a one-time session store is created, the current session key is saved in it, and the
        session store key is added to the redirect URL as a query parameter. If a redirect URL is not provided, the
        success URL defaults to the customer's profile page.

        Args:
            redirect_to (str, optional): The URL to which the user should be redirected. Defaults to None.

        Returns:
            str: The success URL.
        """
        url = self.get_redirect_url(redirect_to)
        # If no redirect URL is provided, default to the customer's profile page
        if not url:
            return eventreverse(self.request.organizer, 'presale:organizer.customer.profile', kwargs={})

        # If a cross-domain customer authentication request is indicated in the session
        if self.request.session.get(f'eventyay_customer_auth_{self.provider.pk}_cross_domain_requested'):
            # Create a one-time session store
            ss_store = SessionStore()

            # Save the current session key in the session store
            ss_store[f'customer_cross_domain_auth_{self.request.organizer.pk}'] = self.request.session.session_key

            # Set the session store to expire in 60 seconds
            ss_store.set_expiry(60)

            # Save the session store
            ss_store.save(must_create=True)

            # Get the session store key
            otp = ss_store.session_key

            # Parse the redirect URL
            u = urlparse(url)

            # Get the query string as a dictionary
            qsl = parse_qs(u.query)

            # Add the session store key to the query string
            qsl['cross_domain_customer_auth'] = otp

            # Reconstruct the redirect URL with the updated query string
            url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(qsl, doseq=True), u.fragment))

        return url


class OrderView(CustomerRequiredMixin, ListView):
    template_name = 'pretixpresale/organizers/customer_order.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = Order.objects.filter(
            Q(customer=self.request.customer)
            | Q(email__iexact=self.request.customer.email)
        ).select_related('event').order_by('-datetime')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_paginated'] = True

        s = OrderPosition.objects.filter(
            order=OuterRef('pk')
        ).order_by().values('order').annotate(k=Count('id')).values('k')
        annotated = {
            o['pk']: o
            for o in
            Order.annotate_overpayments(Order.objects, sums=True).filter(
                pk__in=[o.pk for o in ctx['orders']]
            ).annotate(
                pcnt=Subquery(s, output_field=IntegerField()),
            ).values(
                'pk', 'pcnt',
            )
        }

        for o in ctx['orders']:
            if o.pk not in annotated:
                continue
            o.count_positions = annotated.get(o.pk)['pcnt']
        return ctx
