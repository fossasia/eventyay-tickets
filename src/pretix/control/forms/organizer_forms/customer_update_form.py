from django import forms
from django.utils.translation import gettext_lazy as _

from pretix.base.forms.questions import NamePartsFormField
from pretix.base.models.customers import Customer


class CustomerUpdateForm(forms.ModelForm):
    error_messages = {
        'duplicate': _("An account with this email address is already existed."),
    }

    class Meta:
        model = Customer
        fields = [
            'is_active',
            'name_parts',
            'email',
            'is_verified',
            'locale',
            'external_identifier']

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
        """
        Validates the email and identifier fields to ensure they are unique within the organizer's customers,
        excluding the current instance. Raises a validation error if a duplicate is found.
        """
        email = self.cleaned_data.get('email')
        identifier = self.cleaned_data.get('identifier')

        def check_duplicate(field_name, error_message_key, error_code, field_value):
            if field_value:
                filter_args = {field_name: field_value}
                if self.instance.organizer.customers.exclude(pk=self.instance.pk).filter(**filter_args).exists():
                    raise forms.ValidationError(
                        self.error_messages[error_message_key],
                        code=error_code
                    )

        # Check for duplicate email
        check_duplicate('email', 'duplicate', 'duplicate', email)

        # Check for duplicate identifier
        check_duplicate('identifier', 'duplicate_identifier', 'duplicate_identifier', identifier)

        return self.cleaned_data
