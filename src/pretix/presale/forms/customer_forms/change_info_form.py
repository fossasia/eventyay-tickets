from django import forms
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from pretix.base.forms.questions import NamePartsFormField
from pretix.base.models.customers import Customer


class ChangeInfoForm(forms.ModelForm):
    required_css_class = 'required'
    error_messages = {
        'pw_current_wrong': _("The current password you entered was not correct."),
        'rate_limit': _("For security reasons, please wait 5 minutes before you try again."),
        'duplicate': _("An account with this email address is already registered."),
    }
    password_current = forms.CharField(
        label=_('Your current password'),
        widget=forms.PasswordInput,
        help_text=_('Only required if you change your email address'),
        required=False
    )

    class Meta:
        model = Customer
        fields = ('name_parts', 'email')

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
        if self.instance.provider_id is not None:
            self.fields['email'].disabled = True
            self.fields['email'].help_text = _(
                'To change your email address, change it in your {provider} account and then log out and log in '
                'again.'
            ).format(provider=escape(self.instance.provider.name))
            del self.fields['password_current']

    def clean_password_current(self):
        old_pw = self.cleaned_data.get('password_current')

        if old_pw:
            if settings.HAS_REDIS:
                from django_redis import get_redis_connection

                rc = get_redis_connection("redis")
                cnt = rc.incr('pretix_pwchange_customer_%s' % self.instance.pk)
                rc.expire('pretix_pwchange_customer_%s' % self.instance.pk, 300)
                if cnt > 10:
                    raise forms.ValidationError(
                        self.error_messages['rate_limit'],
                        code='rate_limit',
                    )

            if not check_password(old_pw, self.instance.password):
                raise forms.ValidationError(
                    self.error_messages['pw_current_wrong'],
                    code='pw_current_wrong',
                )

            return "***valid***"

    def clean(self):
        email = self.cleaned_data.get('email')
        password_current = self.cleaned_data.get('password_current')

        if email != self.instance.email and not password_current and self.instance.provider_id is None:
            raise forms.ValidationError(
                self.error_messages['pw_current_wrong'],
                code='pw_current_wrong',
            )

        if email is not None and self.instance.provider_id is not None:
            try:
                self.request.organizer.customers.exclude(pk=self.instance.pk).get(email=email)
            except Customer.DoesNotExist:
                pass
            else:
                raise forms.ValidationError(
                    self.error_messages['duplicate'],
                    code='duplicate',
                )

        return self.cleaned_data
