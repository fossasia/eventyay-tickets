import hashlib
import ipaddress

from django import forms
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from pretix.base.forms.questions import NamePartsFormField
from pretix.base.i18n import get_language_without_region
from pretix.base.models.customers import Customer
from pretix.helpers.http import get_client_ip


class RegistrationForm(forms.Form):
    required_css_class = 'required'
    name_parts = forms.CharField()
    email = forms.EmailField(
        label=_("E-mail"),
    )

    error_messages = {
        'rate_limit': _(
            "We've received a lot of registration requests from you, please wait 10 minutes before you try again."),
        'duplicate': _(
            "An account with this email address is already registered. Please try to log in or reset your password "
            "instead."
        ),
        'required': _('This field is required.'),
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

        self.fields['name_parts'] = NamePartsFormField(
            max_length=255,
            required=True,
            scheme=request.organizer.settings.name_scheme,
            titles=request.organizer.settings.name_scheme_titles,
            label=_('Name'),
        )

    @cached_property
    def ratelimit_key(self):
        if not settings.HAS_REDIS:
            return None
        client_ip = get_client_ip(self.request)
        if not client_ip:
            return None
        try:
            client_ip = ipaddress.ip_address(client_ip)
        except ValueError:
            # Web server not set up correctly
            return None
        if client_ip.is_private:
            # This is the private IP of the server, web server not set up correctly
            return None
        return 'pretix_customer_registration_{}'.format(hashlib.sha1(str(client_ip).encode()).hexdigest())

    def clean(self):
        email = self.cleaned_data.get('email')

        if email is not None:
            try:
                self.request.organizer.customers.get(email=email)
            except Customer.DoesNotExist:
                pass
            else:
                raise forms.ValidationError(
                    {'email': self.error_messages['duplicate']},
                    code='duplicate',
                )

        if not self.cleaned_data.get('email'):
            raise forms.ValidationError(
                {'email': self.error_messages['required']},
                code='incomplete'
            )
        else:
            if self.ratelimit_key:
                from django_redis import get_redis_connection

                rc = get_redis_connection("redis")
                cnt = rc.incr(self.ratelimit_key)
                rc.expire(self.ratelimit_key, 600)
                if cnt > 10:
                    raise forms.ValidationError(
                        self.error_messages['rate_limit'],
                        code='rate_limit',
                    )
        return self.cleaned_data

    def create(self):
        customer = self.request.organizer.customers.create(
            email=self.cleaned_data['email'],
            name_parts=self.cleaned_data['name_parts'],
            is_active=True,
            is_verified=False,
            locale=get_language_without_region(),
        )
        customer.set_unusable_password()
        customer.save()
        customer.log_action('pretix.customer.created', {})
        customer.send_activation_mail()
        return customer
