from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from eventyay.cfp.forms.cfp import CfPFormMixin
from eventyay.common.forms.fields import NewPasswordConfirmationField, NewPasswordField
from eventyay.common.forms.renderers import InlineFormLabelRenderer
from eventyay.common.text.phrases import phrases
from eventyay.base.models import User


class UserForm(CfPFormMixin, forms.Form):
    default_renderer = InlineFormLabelRenderer

    login_email = forms.EmailField(
        max_length=60,
        label=phrases.base.enter_email,
        required=False,
        widget=forms.EmailInput(attrs={'autocomplete': 'username'}),
    )
    login_password = forms.CharField(
        label=_('Password'),
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    register_name = forms.CharField(
        label=_('Name') + f' ({_("display name")})',
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'name'}),
    )
    register_email = forms.EmailField(
        label=phrases.base.enter_email,
        required=False,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )
    register_password = NewPasswordField(
        label=_('Password'),
        required=False,
    )
    register_password_repeat = NewPasswordConfirmationField(
        label=_('Password (again)'),
        required=False,
        confirm_with='register_password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    FIELDS_ERROR = _('Please fill all fields of either the login or the registration form.')

    def __init__(self, *args, **kwargs):
        kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

    def _clean_login(self, data):
        try:
            uname = User.objects.get(email__iexact=data.get('login_email')).email
        except User.DoesNotExist:  # We do this to avoid timing attacks
            uname = 'user@invalid'

        user = authenticate(username=uname, password=data.get('login_password'))

        if user is None:
            raise ValidationError(
                _(
                    'No user account matches the entered credentials. '
                    'Are you sure that you typed your password correctly?'
                )
            )

        if not user.is_active:
            raise ValidationError(_('Sorry, your account is currently disabled.'))

        data['user_id'] = user.pk

    def _clean_register(self, data):
        if data.get('register_password') != data.get('register_password_repeat'):
            self.add_error(
                'register_password_repeat',
                ValidationError(phrases.base.passwords_differ),
            )

        if User.objects.filter(email__iexact=data.get('register_email')).exists():
            self.add_error(
                'register_email',
                ValidationError(
                    _(
                        'We already have a user with that email address. Did you already register '
                        'before and just need to log in?'
                    )
                ),
            )

    def clean(self):
        data = super().clean()

        if data.get('login_email') and data.get('login_password'):
            self._clean_login(data)
        elif data.get('register_email') and data.get('register_password') and data.get('register_name'):
            self._clean_register(data)
        else:
            raise ValidationError(self.FIELDS_ERROR)

        return data

    def save(self):
        data = self.cleaned_data
        if data.get('login_email') and data.get('login_password'):
            return data['user_id']

        # We already checked that all fields are filled, but sometimes
        # they end up empty regardless. No idea why and how.
        if not (data.get('register_email') and data.get('register_password') and data.get('register_name')):
            raise ValidationError(self.FIELDS_ERROR)

        user = User.objects.create_user(
            name=data.get('register_name').strip(),
            email=data.get('register_email').lower().strip(),
            password=data.get('register_password'),
            locale=translation.get_language(),
            timezone=timezone.get_current_timezone_name(),
        )
        data['user_id'] = user.pk
        return user.pk
