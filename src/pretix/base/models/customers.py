import secrets

from django.conf import settings
from django.contrib.auth.hashers import (
    check_password, is_password_usable, make_password,
)
from django.core.validators import URLValidator
from django.db import models
from django.utils.crypto import get_random_string, salted_hmac
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django_scopes import ScopedManager, scopes_disabled
from i18nfield.fields import I18nCharField

from pretix.base.banlist import banned
from pretix.base.models.base import LoggedModel
from pretix.base.models.fields import MultiStringField
from pretix.base.models.organizer import Organizer
from pretix.base.settings import PERSON_NAME_SCHEMES


class CustomerSSOProvider(LoggedModel):
    METHOD_OIDC = 'oidc'
    METHODS = (
        (METHOD_OIDC, 'OpenID Connect'),
    )

    id = models.BigAutoField(primary_key=True)
    organizer = models.ForeignKey(Organizer, related_name='sso_providers', on_delete=models.CASCADE)
    name = I18nCharField(
        max_length=200,
        verbose_name=_("Provider name"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    button_label = I18nCharField(
        max_length=200,
        verbose_name=_("Login button label"),
    )
    method = models.CharField(
        max_length=190,
        verbose_name=_("Single-sign-on method"),
        null=False, blank=False,
        choices=METHODS,
    )
    configuration = models.JSONField()

    def allow_delete(self):
        return not self.customers.exists()


class Customer(LoggedModel):
    """
    Represents a registered customer of an organizer.
    """
    id = models.BigAutoField(primary_key=True)
    organizer = models.ForeignKey(Organizer, related_name='customers', on_delete=models.CASCADE)
    provider = models.ForeignKey(CustomerSSOProvider, related_name='customers', on_delete=models.PROTECT, null=True,
                                 blank=True)
    identifier = models.CharField(max_length=190, db_index=True, unique=True)
    email = models.EmailField(db_index=True, null=True, blank=False, verbose_name=_('E-mail'), max_length=190)
    password = models.CharField(verbose_name=_('Password'), max_length=128)
    name_cached = models.CharField(max_length=255, verbose_name=_('Full name'), blank=True)
    name_parts = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True, verbose_name=_('Account active'))
    is_verified = models.BooleanField(default=True, verbose_name=_('Verified email address'))
    last_login = models.DateTimeField(verbose_name=_('Last login'), blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name=_('Registration date'))
    locale = models.CharField(max_length=50,
                              choices=settings.LANGUAGES,
                              default=settings.LANGUAGE_CODE,
                              verbose_name=_('Language'))
    last_modified = models.DateTimeField(auto_now=True)
    external_identifier = models.CharField(max_length=255, verbose_name=_('External identifier'), null=True, blank=True)

    objects = ScopedManager(organizer='organizer')

    class Meta:
        unique_together = [['organizer', 'email'], ['organizer', 'identifier']]
        ordering = ('email',)

    def get_email_field_name(self):
        """
        Returns the name of the field that stores the email.
        @return: string
        """
        return 'email'

    def save(self, **kwargs):
        if self.email:
            self.email = self.email.lower()
        if 'update_fields' in kwargs and 'last_modified' not in kwargs['update_fields']:
            kwargs['update_fields'] = {'last_modified'}.union(kwargs['update_fields'])
        if not self.identifier:
            self.generate_identifier()
        if self.name_parts:
            self.name_cached = self.name
        else:
            self.name_cached = ""
            self.name_parts = {}
        super().save(**kwargs)

    def anonymize_customer(self):
        """
        Anonymize the customer, remove all personal data.
        """
        self.is_active = False
        self.is_verified = False
        self.name_parts = {}
        self.name_cached = ''
        self.email = None
        self.external_identifier = None
        self.save()
        self.all_logentries().update(data={}, shredded=True)
        self.orders.all().update(customer=None)

    @scopes_disabled()
    def generate_identifier(self):
        """
        Assigns a unique identifier to a customer.

        This method generates a random identifier using a specified character set and ensures
        that the generated identifier is not banned and does not already exist in the database.
        If the identifier generation fails after multiple iterations, the length of the identifier
        is increased to ensure uniqueness.

        Raises:
            ValueError: If a unique identifier could not be generated after multiple attempts.
        """
        iteration = 0
        length = settings.ENTROPY['customer_identifier']

        def generate_random_identifier(length):
            code = secrets.token_hex(4)[:length].upper()
            if (banned(code)):
                length += 1
                if length > Customer.identifier.field.max_length:
                    raise ValueError("Unable to generate a unique identifier.")
                return generate_random_identifier(length)
            return code

        while iteration < 20:
            code = generate_random_identifier(length=length)
            iteration += 1

            # Check if the code is unique
            if not Customer.objects.filter(identifier=code).exists():
                self.identifier = code
                return

        raise ValueError("Unable to generate a unique identifier.")

    @property
    def name(self):
        """
        Concatenates and returns the customer's name based on the name parts.

        This property constructs the full name of a customer using the `name_parts` dictionary.
        If `_legacy` is present in `name_parts`, it returns the legacy name.
        If `_scheme` is present, it uses the corresponding scheme to concatenate the name parts.
        If neither `_legacy` nor `_scheme` is present, it raises a TypeError.

        Returns:
            str: The concatenated name of the customer.

        Raises:
            TypeError: If `name_parts` is invalid or missing required keys.
        """
        if not self.name_parts:
            return ""

        if '_legacy' in self.name_parts:
            return self.name_parts['_legacy']

        if '_scheme' in self.name_parts:
            scheme = PERSON_NAME_SCHEMES[self.name_parts['_scheme']]
        else:
            raise TypeError("Invalid name given.")

        return scheme['concatenation'](self.name_parts).strip()

    def __str__(self):
        s = f'#{self.identifier}'
        if self.name or self.email:
            s += f' – {self.name or self.email}'
        if not self.is_active:
            s += f' ({_("disabled")})'
        return s

    def set_password(self, raw_password):
        """
        Sets the password for the customer.
        @param raw_password: input password
        """
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """
        Checks if the provided raw password matches the stored hashed password.

        This method uses Django's `check_password` utility to verify the password. If the password needs
        to be rehashed, it uses the provided setter to update the stored password.

        Args:
            raw_password (str): The raw password to check.

        Returns:
            bool: True if the password is correct, False otherwise.
        """

        def setter(raw_password):
            self.set_password(raw_password)
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        """
        Sets the password to an unusable value.
        """
        self.password = make_password(None)

    def has_usable_password(self):
        """
        Checks if the customer has a usable password.
        @return:
        """
        return is_password_usable(self.password)

    def get_session_auth_hash(self):
        key_salt = "$2a$12$9yg2Pg.pJOnOzO9Ysxx7aO/xznE3yhBIl5h3i4i9pz1uRDSDwBska"
        payload = self.password
        payload += self.email
        return salted_hmac(key_salt, payload).hexdigest()

    def get_email_context(self):
        """
        Generates the context for email templates related to the customer.

        This method constructs a dictionary with key-value pairs representing the
        customer's name and organizer's name. It also includes individual parts of
        the customer's name based on the defined name scheme.

        Returns:
            dict: A dictionary containing the context for email templates.
        """
        # Initialize the context with the customer's name and organizer's name
        ctx = {
            'name': self.name,
            'organizer': self.organizer.name,
        }

        # Retrieve the name scheme for the organizer
        name_scheme = PERSON_NAME_SCHEMES[self.organizer.settings.name_scheme]

        # Add individual name parts to the context based on the name scheme
        for f, l, w in name_scheme['fields']:
            if f == 'full_name':
                continue
            ctx['name_%s' % f] = self.name_parts.get(f, '')
        return ctx

    def send_activation_mail(self):
        """
        Sends an activation email to the customer.
        """
        from pretix.base.services.mail import mail
        from pretix.multidomain.urlreverse import build_absolute_uri
        from pretix.presale.forms.customer import TokenGenerator

        ctx = self.get_email_context()
        token = TokenGenerator().make_token(self)
        ctx['url'] = build_absolute_uri(
            self.organizer,
            'presale:organizer.customer.activate'
        ) + '?id=' + self.identifier + '&token=' + token
        mail(
            self.email,
            self.organizer.settings.mail_subject_customer_registration,
            self.organizer.settings.mail_text_customer_registration,
            ctx,
            locale=self.locale,
            customer=self,
            organizer=self.organizer,
        )


def generate_client_id():
    return get_random_string(40)


def generate_client_secret():
    return get_random_string(40)


class CustomerSSOClient(LoggedModel):
    CLIENT_CONFIDENTIAL = "confidential"
    CLIENT_PUBLIC = "public"
    CLIENT_TYPES = (
        (CLIENT_CONFIDENTIAL, pgettext_lazy("openidconnect", "Confidential")),
        (CLIENT_PUBLIC, pgettext_lazy("openidconnect", "Public")),
    )

    GRANT_AUTHORIZATION_CODE = "authorization-code"
    GRANT_IMPLICIT = "implicit"
    GRANT_TYPES = (
        (GRANT_AUTHORIZATION_CODE, pgettext_lazy("openidconnect", "Authorization code")),
        (GRANT_IMPLICIT, pgettext_lazy("openidconnect", "Implicit")),
    )

    SCOPE_CHOICES = (
        ('openid', _('OpenID Connect access (required)')),
        ('profile', _('Profile data (name, addresses)')),
        ('email', _('E-mail address')),
        ('phone', _('Phone number')),
    )

    id = models.BigAutoField(primary_key=True)
    organizer = models.ForeignKey(Organizer, related_name='sso_clients', on_delete=models.CASCADE)

    name = models.CharField(verbose_name=_("Application name"), max_length=255, blank=False)
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))

    client_id = models.CharField(
        verbose_name=_("Client ID"),
        max_length=100, unique=True, default=generate_client_id, db_index=True
    )
    client_secret = models.CharField(
        max_length=255, blank=False,
    )

    client_type = models.CharField(
        max_length=32, choices=CLIENT_TYPES, verbose_name=_("Client type"), default=CLIENT_CONFIDENTIAL,
    )
    authorization_grant_type = models.CharField(
        max_length=32, choices=GRANT_TYPES, verbose_name=_("Grant type"), default=GRANT_AUTHORIZATION_CODE,
    )
    redirect_uris = models.TextField(
        blank=False,
        verbose_name=_("Redirection URIs"),
        help_text=_("Allowed URIs list, space separated")
    )
    allowed_scopes = MultiStringField(
        default=['openid', 'profile', 'email', 'phone'],
        delimiter=" ",
        blank=True,
        verbose_name=_('Allowed access scopes'),
        help_text=_('Separate multiple values with spaces'),
    )

    def is_usable(self):
        return self.is_active

    def allow_redirect_uri(self, redirect_uri):
        return self.redirect_uris and any(r.strip() == redirect_uri for r in self.redirect_uris.split(' '))

    def allow_delete(self):
        return True

    def evaluated_scope(self, scope):
        scope = set(scope.split(' '))
        allowed_scopes = set(self.allowed_scopes)
        return ' '.join(scope & allowed_scopes)

    def clean(self):
        redirect_uris = self.redirect_uris.strip().split()

        if redirect_uris:
            validator = URLValidator()
            for uri in redirect_uris:
                validator(uri)

    def set_client_secret(self):
        secret = get_random_string(64)
        self.client_secret = make_password(secret)
        return secret

    def check_client_secret(self, raw_secret):
        def setter(raw_secret):
            self.client_secret = make_password(raw_secret)
            self.save(update_fields=["client_secret"])

        return check_password(raw_secret, self.client_secret, setter)


class CustomerSSOGrant(models.Model):
    id = models.BigAutoField(primary_key=True)
    client = models.ForeignKey(
        CustomerSSOClient, on_delete=models.CASCADE, related_name="grants"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="sso_grants"
    )
    code = models.CharField(max_length=255, unique=True)
    nonce = models.CharField(max_length=255, null=True, blank=True)
    auth_time = models.IntegerField()
    expires = models.DateTimeField()
    redirect_uri = models.TextField()
    scope = models.TextField(blank=True)


class CustomerSSOAccessToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    client = models.ForeignKey(
        CustomerSSOClient, on_delete=models.CASCADE, related_name="access_tokens"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="sso_access_tokens"
    )
    from_code = models.CharField(max_length=255, null=True, blank=True)
    token = models.CharField(max_length=255, unique=True)
    expires = models.DateTimeField()
    scope = models.TextField(blank=True)
