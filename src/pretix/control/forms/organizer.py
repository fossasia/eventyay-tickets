from decimal import Decimal
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.forms import I18nFormField, I18nTextarea
from pytz import common_timezones

from pretix.api.models import WebHook
from pretix.api.webhooks import get_all_webhook_events
from pretix.base.forms import I18nModelForm, PlaceholderValidator, SettingsForm
from pretix.base.forms.questions import NamePartsFormField
from pretix.base.customersso.oidc import oidc_validate_and_complete_config
from pretix.base.forms.widgets import SplitDateTimePickerWidget
from pretix.base.models import (
    Customer, Device, EventMetaProperty, Gate, GiftCard, Organizer, Team,
)
from pretix.base.models.customers import CustomerSSOClient, CustomerSSOProvider
from pretix.base.settings import PERSON_NAME_SCHEMES, PERSON_NAME_TITLE_GROUPS
from pretix.control.forms import ExtFileField, SplitDateTimeField
from pretix.control.forms import (
    SMTPSettingsMixin, )
from pretix.control.forms.event import SafeEventMultipleChoiceField
from pretix.control.forms.event import (
    multimail_validate,
)
from pretix.multidomain.models import KnownDomain
from pretix.multidomain.urlreverse import build_absolute_uri


class OrganizerForm(I18nModelForm):
    error_messages = {
        'duplicate_slug': _("This slug is already in use. Please choose a different one."),
    }

    class Meta:
        model = Organizer
        fields = ['name', 'slug']

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Organizer.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                self.error_messages['duplicate_slug'],
                code='duplicate_slug',
            )
        return slug


class OrganizerDeleteForm(forms.Form):
    error_messages = {
        'slug_wrong': _("The slug you entered was not correct."),
    }
    slug = forms.CharField(
        max_length=255,
        label=_("Event slug"),
    )

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if slug != self.organizer.slug:
            raise forms.ValidationError(
                self.error_messages['slug_wrong'],
                code='slug_wrong',
            )
        return slug


class OrganizerUpdateForm(OrganizerForm):

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain', False)
        self.change_slug = kwargs.pop('change_slug', False)
        kwargs.setdefault('initial', {})
        self.instance = kwargs['instance']
        if self.domain and self.instance:
            initial_domain = self.instance.domains.filter(event__isnull=True).first()
            if initial_domain:
                kwargs['initial'].setdefault('domain', initial_domain.domainname)

        super().__init__(*args, **kwargs)
        if not self.change_slug:
            self.fields['slug'].widget.attrs['readonly'] = 'readonly'
        if self.domain:
            self.fields['domain'] = forms.CharField(
                max_length=255,
                label=_('Custom domain'),
                required=False,
                help_text=_('You need to configure the custom domain in the webserver beforehand.')
            )

    def clean_domain(self):
        d = self.cleaned_data['domain']
        if d:
            if d == urlparse(settings.SITE_URL).hostname:
                raise ValidationError(
                    _('You cannot choose the base domain of this installation.')
                )
            if KnownDomain.objects.filter(domainname=d).exclude(organizer=self.instance.pk,
                                                                event__isnull=True).exists():
                raise ValidationError(
                    _('This domain is already in use for a different event or organizer.')
                )
        return d

    def clean_slug(self):
        if self.change_slug:
            return self.cleaned_data['slug']
        return self.instance.slug

    def save(self, commit=True):
        instance = super().save(commit)

        if self.domain:
            current_domain = instance.domains.first()
            if self.cleaned_data['domain']:
                if current_domain and current_domain.domainname != self.cleaned_data['domain']:
                    current_domain.delete()
                    KnownDomain.objects.create(organizer=instance, domainname=self.cleaned_data['domain'])
                elif not current_domain:
                    KnownDomain.objects.create(organizer=instance, domainname=self.cleaned_data['domain'])
            elif current_domain:
                current_domain.delete()
            instance.cache.clear()
            for ev in instance.events.all():
                ev.cache.clear()

        return instance


class EventMetaPropertyForm(forms.ModelForm):
    class Meta:
        model = EventMetaProperty
        fields = ['name', 'default', 'required', 'protected', 'allowed_values']
        widgets = {
            'default': forms.TextInput()
        }


class TeamForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all().order_by(
            '-has_subevents', '-date_from'
        )

    class Meta:
        model = Team
        fields = ['name', 'all_events', 'limit_events', 'can_create_events',
                  'can_change_teams', 'can_change_organizer_settings',
                  'can_manage_gift_cards', 'can_manage_customers',
                  'can_change_event_settings', 'can_change_items',
                  'can_view_orders', 'can_change_orders', 'can_checkin_orders',
                  'can_view_vouchers', 'can_change_vouchers']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(attrs={
                'data-inverse-dependency': '#id_all_events',
                'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
            }),
        }
        field_classes = {
            'limit_events': SafeEventMultipleChoiceField
        }

    def clean(self):
        data = super().clean()
        if self.instance.pk and not data['can_change_teams']:
            if not self.instance.organizer.teams.exclude(pk=self.instance.pk).filter(
                    can_change_teams=True, members__isnull=False
            ).exists():
                raise ValidationError(_('The changes could not be saved because there would be no remaining team with '
                                        'the permission to change teams and permissions.'))

        return data


class GateForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        kwargs.pop('organizer')
        super().__init__(*args, **kwargs)

    class Meta:
        model = Gate
        fields = ['name', 'identifier']


class DeviceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all().order_by(
            '-has_subevents', '-date_from'
        )
        self.fields['gate'].queryset = organizer.gates.all()

    def clean(self):
        d = super().clean()
        if not d['all_events'] and not d['limit_events']:
            raise ValidationError(_('Your device will not have access to anything, please select some events.'))

        return d

    class Meta:
        model = Device
        fields = ['name', 'all_events', 'limit_events', 'security_profile', 'gate']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(attrs={
                'data-inverse-dependency': '#id_all_events',
                'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
            }),
        }
        field_classes = {
            'limit_events': SafeEventMultipleChoiceField
        }


class OrganizerSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_("Default timezone"),
    )
    name_scheme = forms.ChoiceField(
        label=_("Name format"),
        help_text=_("Changing this after you already received "
                    "orders might lead to unexpected behavior when sorting or changing names."),
        required=True,
    )
    name_scheme_titles = forms.ChoiceField(
        label=_("Allowed titles"),
        help_text=_("If the naming scheme you defined above allows users to input a title, you can use this to "
                    "restrict the set of selectable titles."),
        required=False,
    )
    auto_fields = [
        'customer_accounts',
        'customer_accounts_native',
        'contact_mail',
        'imprint_url',
        'organizer_info_text',
        'event_list_type',
        'event_list_availability',
        'organizer_homepage_text',
        'organizer_link_back',
        'organizer_logo_image_large',
        'giftcard_length',
        'giftcard_expiry_years',
        'locales',
        'region',
        'event_team_provisioning',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'theme_round_borders',
        'primary_font'

    ]

    organizer_logo_image = ExtFileField(
        label=_('Header image'),
        ext_whitelist=(".png", ".jpg", ".gif", ".jpeg"),
        max_size=10 * 1024 * 1024,
        required=False,
        help_text=_('If you provide a logo image, we will by default not show your organization name '
                    'in the page header. By default, we show your logo with a size of up to 1140x120 pixels. You '
                    'can increase the size with the setting below. We recommend not using small details on the picture '
                    'as it will be resized on smaller screens.')
    )
    favicon = ExtFileField(
        label=_('Favicon'),
        ext_whitelist=(".ico", ".png", ".jpg", ".gif", ".jpeg"),
        required=False,
        max_size=1 * 1024 * 1024,
        help_text=_('If you provide a favicon, we will show it instead of the default pretix icon. '
                    'We recommend a size of at least 200x200px to accommodate most devices.')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name_scheme'].choices = (
            (k, _('Ask for {fields}, display like {example}').format(
                fields=' + '.join(str(vv[1]) for vv in v['fields']),
                example=v['concatenation'](v['sample'])
            ))
            for k, v in PERSON_NAME_SCHEMES.items()
        )
        self.fields['name_scheme_titles'].choices = [('', _('Free text input'))] + [
            (k, '{scheme}: {samples}'.format(
                scheme=v[0],
                samples=', '.join(v[1])
            ))
            for k, v in PERSON_NAME_TITLE_GROUPS.items()
        ]


class MailSettingsForm(SMTPSettingsMixin, SettingsForm):
    auto_fields = [
        'mail_from',
        'mail_from_name',
    ]

    mail_bcc = forms.CharField(
        label=_("Bcc address"),
        help_text=_("All emails will be sent to this address as a Bcc copy"),
        validators=[multimail_validate],
        required=False,
        max_length=255
    )
    mail_text_signature = I18nFormField(
        label=_("Signature"),
        required=False,
        widget=I18nTextarea,
        help_text=_("This will be attached to every email."),
        validators=[PlaceholderValidator([])],
        widget_kwargs={'attrs': {
            'rows': '4',
            'placeholder': _(
                'e.g. your contact details'
            )
        }}
    )

    mail_text_customer_registration = I18nFormField(
        label=_("Text"),
        required=False,
        widget=I18nTextarea,
    )
    mail_subject_customer_registration = I18nFormField(
        label=_("Subject"),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_customer_email_change = I18nFormField(
        label=_("Text"),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_customer_reset = I18nFormField(
        label=_("Text"),
        required=False,
        widget=I18nTextarea,
    )

    base_context = {
        'mail_text_customer_registration': ['customer', 'url'],
        'mail_text_customer_email_change': ['customer', 'url'],
        'mail_text_customer_reset': ['customer', 'url'],
    }

    def _get_sample_context(self, base_parameters):
        placeholders = {
            'organizer': self.organizer.name
        }

        if 'url' in base_parameters:
            placeholders['url'] = build_absolute_uri(
                self.organizer,
                'presale:organizer.customer.activate'
            ) + '?token=' + get_random_string(30)

        if 'customer' in base_parameters:
            placeholders['name'] = pgettext_lazy('person_name_sample', 'John Doe')
            name_scheme = PERSON_NAME_SCHEMES[self.organizer.settings.name_scheme]
            for f, l, w in name_scheme['fields']:
                if f == 'full_name':
                    continue
                placeholders['name_%s' % f] = name_scheme['sample'][f]
        return placeholders

    def _set_field_placeholders(self, fn, base_parameters):
        phs = [
            '{%s}' % p
            for p in sorted(self._get_sample_context(base_parameters).keys())
        ]
        ht = _('Available placeholders: {list}').format(
            list=', '.join(phs)
        )
        if self.fields[fn].help_text:
            self.fields[fn].help_text += ' ' + str(ht)
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(
            PlaceholderValidator(phs)
        )

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        for k, v in self.base_context.items():
            self._set_field_placeholders(k, v)


class WebHookForm(forms.ModelForm):
    events = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        label=pgettext_lazy('webhooks', 'Event types')
    )

    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all()
        self.fields['events'].choices = [
            (
                a.action_type,
                mark_safe('{} – <code>{}</code>'.format(a.verbose_name, a.action_type))
            ) for a in get_all_webhook_events().values()
        ]
        if self.instance and self.instance.pk:
            self.fields['events'].initial = list(self.instance.listeners.values_list('action_type', flat=True))

    class Meta:
        model = WebHook
        fields = ['target_url', 'enabled', 'all_events', 'limit_events']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(attrs={
                'data-inverse-dependency': '#id_all_events'
            }),
        }
        field_classes = {
            'limit_events': SafeModelMultipleChoiceField
        }


class GiftCardCreateForm(forms.ModelForm):
    value = forms.DecimalField(
        label=_('Gift card value'),
        min_value=Decimal('0.00')
    )

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer')
        initial = kwargs.pop('initial', {})
        initial['expires'] = self.organizer.default_gift_card_expiry
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def clean_secret(self):
        s = self.cleaned_data['secret']
        if GiftCard.objects.filter(
                secret__iexact=s
        ).filter(
            Q(issuer=self.organizer) | Q(issuer__gift_card_collector_acceptance__collector=self.organizer)
        ).exists():
            raise ValidationError(
                _('A gift card with the same secret already exists in your or an affiliated organizer account.')
            )
        return s

    class Meta:
        model = GiftCard
        fields = ['secret', 'currency', 'testmode', 'expires', 'conditions']
        field_classes = {
            'expires': SplitDateTimeField
        }
        widgets = {
            'expires': SplitDateTimePickerWidget,
            'conditions': forms.Textarea(attrs={"rows": 2})
        }


class GiftCardUpdateForm(forms.ModelForm):
    class Meta:
        model = GiftCard
        fields = ['expires', 'conditions']
        field_classes = {
            'expires': SplitDateTimeField
        }
        widgets = {
            'expires': SplitDateTimePickerWidget,
            'conditions': forms.Textarea(attrs={"rows": 2})
        }


class CustomerUpdateForm(forms.ModelForm):
    error_messages = {
        'duplicate': _("An account with this email address is already registered."),
    }

    class Meta:
        model = Customer
        fields = ['is_active', 'name_parts', 'email', 'is_verified', 'locale', 'external_identifier']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['name_parts'] = NamePartsFormField(
            max_length=255,
            required=False,
            scheme=self.instance.organizer.settings.name_scheme,
            titles=self.instance.organizer.settings.name_scheme_titles,
            label=_('Name'),
        )
        if self.instance.provider_id:
            self.fields['email'].disabled = True
            self.fields['is_verified'].disabled = True
            self.fields['external_identifier'].disabled = True

    def clean(self):
        email = self.cleaned_data.get('email')
        identifier = self.cleaned_data.get('identifier')

        if email is not None:
            try:
                self.instance.organizer.customers.exclude(pk=self.instance.pk).get(email=email)
            except Customer.DoesNotExist:
                pass
            else:
                raise forms.ValidationError(
                    self.error_messages['duplicate'],
                    code='duplicate',
                )

        if identifier is not None:
            try:
                self.instance.organizer.customers.exclude(pk=self.instance.pk).get(identifier=identifier)
            except Customer.DoesNotExist:
                pass
            else:
                raise forms.ValidationError(
                    self.error_messages['duplicate_identifier'],
                    code='duplicate_identifier',
                )

        return self.cleaned_data


class SSOProviderForm(I18nModelForm):

    config_oidc_base_url = forms.URLField(
        label=pgettext_lazy('sso_oidc', 'Base URL'),
        required=False,
    )
    config_oidc_client_id = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Client ID'),
        required=False,
    )
    config_oidc_client_secret = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Client secret'),
        required=False,
    )
    config_oidc_scope = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Scope'),
        help_text=pgettext_lazy('sso_oidc', 'Multiple scopes separated with spaces.'),
        required=False,
    )
    config_oidc_uid_field = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'User ID field'),
        help_text=pgettext_lazy('sso_oidc', 'We will assume that the contents of the user ID fields are unique and '
                                            'can never change for a user.'),
        required=True,
        initial='sub',
    )
    config_oidc_email_field = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Email field'),
        help_text=pgettext_lazy('sso_oidc', 'We will assume that all email addresses received from the SSO provider '
                                            'are verified to really belong the the user. If this can\'t be '
                                            'guaranteed, security issues might arise.'),
        required=True,
        initial='email',
    )
    config_oidc_phone_field = forms.CharField(
        label=pgettext_lazy('sso_oidc', 'Phone field'),
        required=False,
    )

    class Meta:
        model = CustomerSSOProvider
        fields = ['is_active', 'name', 'button_label', 'method']
        widgets = {
            'method': forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        name_scheme = self.event.settings.name_scheme
        scheme = PERSON_NAME_SCHEMES.get(name_scheme)
        for fname, label, size in scheme['fields']:
            self.fields[f'config_oidc_{fname}_field'] = forms.CharField(
                label=pgettext_lazy('sso_oidc', f'{label} field').format(label=label),
                required=False,
            )

        self.fields['method'].choices = [c for c in self.fields['method'].choices if c[0]]

        for fname, f in self.fields.items():
            if fname.startswith('config_'):
                prefix, method, suffix = fname.split('_', 2)
                f.widget.attrs['data-display-dependency'] = f'input[name=method][value={method}]'

                if self.instance and self.instance.method == method:
                    f.initial = self.instance.configuration.get(suffix)

    def clean(self):
        data = self.cleaned_data
        if not data.get("method"):
            return data

        config = {}
        for fname, f in self.fields.items():
            if fname.startswith(f'config_{data["method"]}_'):
                prefix, method, suffix = fname.split('_', 2)
                config[suffix] = data.get(fname)

        if data["method"] == "oidc":
            oidc_validate_and_complete_config(config)

        self.instance.configuration = config


class SSOClientForm(I18nModelForm):
    regenerate_client_secret = forms.BooleanField(
        label=_('Invalidate old client secret and generate a new one'),
        required=False,
    )

    class Meta:
        model = CustomerSSOClient
        fields = ['is_active', 'name', 'client_id', 'client_type', 'authorization_grant_type', 'redirect_uris',
                  'allowed_scopes']
        widgets = {
            'authorization_grant_type': forms.RadioSelect,
            'client_type': forms.RadioSelect,
            'allowed_scopes': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_scopes'] = forms.MultipleChoiceField(
            label=self.fields['allowed_scopes'].label,
            help_text=self.fields['allowed_scopes'].help_text,
            required=self.fields['allowed_scopes'].required,
            initial=self.fields['allowed_scopes'].initial,
            choices=CustomerSSOClient.SCOPE_CHOICES,
            widget=forms.CheckboxSelectMultiple
        )
        if self.instance and self.instance.pk:
            self.fields['client_id'].disabled = True
        else:
            del self.fields['client_id']
            del self.fields['regenerate_client_secret']
