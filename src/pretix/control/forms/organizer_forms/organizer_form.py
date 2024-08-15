from django import forms
from django.utils.translation import gettext_lazy as _

from pretix.base.forms import I18nModelForm
from pretix.base.models.organizer import Organizer


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
