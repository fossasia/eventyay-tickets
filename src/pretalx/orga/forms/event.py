from django import forms
from django.utils.timezone import get_current_timezone_name

from pretalx.event.models import Event
from pretalx.person.models import EventPermission, User


class EventForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(queryset=User.objects.all())

    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['timezone'] = get_current_timezone_name()
        if read_only:
            for field_name, field in self.fields.items():
                field.disabled = True

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Event.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError('This slug is already taken.')
        return slug.lower()

    def _save_m2m(self):
        new_users = set(self.cleaned_data['permissions'])
        old_users = set(EventPermission.objects.filter(event=self.instance, is_orga=True))

        to_be_removed = old_users - new_users
        to_be_added = new_users - old_users

        for user in to_be_removed:
            EventPermission.objects.get(user=user, event=self.instance, orga=True).delete()

        for user in to_be_added:
            EventPermission.objects.create(user=user, event=self.instance, is_orga=True)

    class Meta:
        model = Event
        fields = [
            'name', 'slug', 'subtitle', 'is_public', 'date_from', 'date_to',
            'timezone', 'email', 'color', 'permissions',
        ]
