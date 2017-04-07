from django import forms
from django.conf import settings
from django.utils.timezone import get_current_timezone_name
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.forms import ReadOnlyFlag
from pretalx.event.models import Event
from pretalx.person.models import EventPermission, User


class EventForm(ReadOnlyFlag, I18nModelForm):
    permissions = forms.ModelMultipleChoiceField(queryset=User.objects.all())
    locales = forms.MultipleChoiceField(
        label=_('Active languages'),
        choices=settings.LANGUAGES,
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['timezone'] = get_current_timezone_name()
        self.initial['locales'] = self.instance.locale_array.split(",")

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Event.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(_('This slug is already taken.'))

        return slug.lower()

    def clean(self):
        data = super().clean()

        if data.get('locale') not in data.get('locales'):
            raise forms.ValidationError(_('Your default language needs to be one of your active languages.'))

        return data

    def save(self, *args, **kwargs):
        self.instance.locale_array = ",".join(self.cleaned_data['locales'])
        return super().save(*args, **kwargs)

    def _save_m2m(self):
        new_users = set(self.cleaned_data['permissions'])
        old_users = set(User.objects.filter(permissions__event=self.instance, permissions__is_orga=True))

        to_be_removed = old_users - new_users
        to_be_added = new_users - old_users

        for user in to_be_removed:
            EventPermission.objects.get(user=user, event=self.instance, is_orga=True).delete()

        for user in to_be_added:
            EventPermission.objects.create(user=user, event=self.instance, is_orga=True)

    class Meta:
        model = Event
        fields = [
            'name', 'slug', 'subtitle', 'is_public', 'date_from', 'date_to',
            'timezone', 'email', 'color', 'permissions', 'locale'
        ]
