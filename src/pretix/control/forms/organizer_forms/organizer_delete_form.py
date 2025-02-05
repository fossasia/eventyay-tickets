from django import forms
from django.utils.translation import gettext_lazy as _


class OrganizerDeleteForm(forms.Form):
    error_messages = {
        'slug_wrong': _('The slug you entered was not correct.'),
    }
    slug = forms.CharField(
        max_length=255,
        label=_('Event slug'),
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
