from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.forms.fields import PasswordConfirmationField, PasswordField
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.person.models import SpeakerInformation, SpeakerProfile, User
from pretalx.schedule.forms import AvailabilitiesFormMixin


class UserForm(forms.Form):
    login_email = forms.EmailField(
        max_length=60, label=phrases.base.enter_email, required=False
    )
    login_password = forms.CharField(
        widget=forms.PasswordInput, label=_('Password'), required=False
    )
    register_email = forms.EmailField(label=_('Email address'), required=False)
    register_password = PasswordField(label=_('Password'), required=False)
    register_password_repeat = PasswordConfirmationField(
        label=_('Password (again)'), required=False, confirm_with='register_password'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['register_email'].widget.attrs = {'placeholder': _('Email address')}

    def _clean_login(self, data):
        try:
            uname = User.objects.get(email=data.get('login_email')).email
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
            raise ValidationError(phrases.base.passwords_differ)

        if User.objects.filter(email__iexact=data.get('register_email')).exists():
            raise ValidationError(
                _(
                    'We already have a user with that email address. Did you already register '
                    'before and just need to log in?'
                )
            )

    def clean(self):
        data = super().clean()

        if data.get('login_email') and data.get('login_password'):
            self._clean_login(data)
        elif data.get('register_email') and data.get('register_password'):
            self._clean_register(data)
        else:
            raise ValidationError(
                _(
                    'You need to fill all fields of either the login or the registration form.'
                )
            )

        return data

    def save(self):
        data = self.cleaned_data
        if data.get('login_email') and data.get('login_password'):
            return data['user_id']

        user = User.objects.create_user(
            email=data.get('register_email'),
            password=data.get('register_password'),
            locale=translation.get_language(),
            timezone=timezone.get_current_timezone_name(),
        )
        data['user_id'] = user.pk
        return user.pk


class SpeakerProfileForm(AvailabilitiesFormMixin, ReadOnlyFlag, forms.ModelForm):
    USER_FIELDS = ['name', 'email', 'avatar', 'get_gravatar']
    FIRST_TIME_EXCLUDE = ['email']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.event = kwargs.pop('event', None)
        self.with_email = kwargs.pop('with_email', True)
        self.essential_only = kwargs.pop('essential_only', False)
        if self.user:
            kwargs['instance'] = self.user.profiles.filter(event=self.event).first()
        else:
            kwargs['instance'] = SpeakerProfile()
        super().__init__(*args, **kwargs, event=self.event)
        read_only = kwargs.get('read_only', False)
        initials = dict()
        if self.event and not self.event.settings.cfp_request_biography:
            self.fields.pop('biography')
        else:
            self.fields[
                'biography'
            ].required = self.event.settings.cfp_require_biography
        if self.user:
            initials = {field: getattr(self.user, field) for field in self.user_fields}
        for field in self.user_fields:
            self.fields[field] = User._meta.get_field(field).formfield(
                initial=initials.get(field), disabled=read_only
            )

    @cached_property
    def user_fields(self):
        if self.user and not self.essential_only:
            return [f for f in self.USER_FIELDS if f != "email" or self.with_email]
        return [
            f
            for f in self.USER_FIELDS
            if f not in self.FIRST_TIME_EXCLUDE and (f != "email" or self.with_email)
        ]

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if (
            avatar
            and avatar.file
            and hasattr(avatar, '_size')
            and avatar._size > 10 * 1024 * 1024
        ):
            raise ValidationError(_('Your avatar may not be larger than 10 MB.'))
        return avatar

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = User.objects.all()
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.filter(email__iexact=email):
            raise ValidationError(
                _('Please choose a different email address, this one is taken.')
            )
        return email

    def save(self, **kwargs):
        for user_attribute in self.user_fields:
            value = self.cleaned_data.get(user_attribute)
            if value is False and user_attribute == 'avatar':
                self.user.avatar = None
            else:
                setattr(self.user, user_attribute, value)
                self.user.save(update_fields=[user_attribute])

        self.instance.event = self.event
        self.instance.user = self.user
        super().save(**kwargs)

    class Meta:
        model = SpeakerProfile
        fields = ('biography',)


class OrgaProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('name', 'locale')


class LoginInfoForm(forms.ModelForm):
    error_messages = {
        'pw_current_wrong': _("The current password you entered was not correct.")
    }

    old_password = forms.CharField(
        widget=forms.PasswordInput, label=_('Password (current)'), required=True
    )
    password = PasswordField(label=_('New password'), required=False)
    password_repeat = PasswordConfirmationField(
        label=phrases.base.password_repeat, required=False, confirm_with='password'
    )

    def clean_old_password(self):
        old_pw = self.cleaned_data.get('old_password')
        if not check_password(old_pw, self.user.password):
            raise forms.ValidationError(
                self.error_messages['pw_current_wrong'], code='pw_current_wrong'
            )
        return old_pw

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email):
            raise ValidationError(_('Please choose a different email address.'))
        return email

    def clean(self):
        super().clean()
        password = self.cleaned_data.get('password')
        if password and not password == self.cleaned_data.get('password_repeat'):
            raise ValidationError(phrases.base.passwords_differ)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs['instance'] = user
        super().__init__(*args, **kwargs)

    def save(self):
        super().save()
        password = self.cleaned_data.get('password')
        if password:
            self.user.set_password(password)
            self.user.save()

    class Meta:
        model = User
        fields = ('email',)


class SpeakerInformationForm(I18nModelForm):
    def clean(self):
        result = super().clean()
        if (
            self.cleaned_data['include_submitters']
            and self.cleaned_data['exclude_unconfirmed']
        ):
            raise ValidationError(
                _(
                    'Either target all submitters or only confirmed speakers, these options are exclusive!'
                )
            )
        return result

    class Meta:
        model = SpeakerInformation
        fields = (
            'title',
            'text',
            'include_submitters',
            'exclude_unconfirmed',
            'resource',
        )


class SpeakerFilterForm(forms.Form):
    role = forms.ChoiceField(
        choices=(
            ('', _('all')),
            ('true', _('Speakers')),
            ('false', _('Non-accepted submitters')),
        ),
        required=False,
    )
