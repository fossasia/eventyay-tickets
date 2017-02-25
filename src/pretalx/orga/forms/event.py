from django import forms
from django.utils.timezone import get_current_timezone_name

from pretalx.event.models import Event
from pretalx.person.models import User


class EventForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(queryset=User.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        import pdb; pdb.set_trace()
        self.initial['timezone'] = get_current_timezone_name()

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Event.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError('This slug is already taken.')
        return slug.lower()

    class Meta:
        model = Event
        fields = [
            'name', 'slug', 'subtitle', 'is_public', 'date_from', 'date_to',
            'timezone', 'email', 'color', 'permissions',
        ]
