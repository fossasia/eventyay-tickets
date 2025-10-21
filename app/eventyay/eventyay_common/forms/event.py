from django import forms
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones
from django.core.exceptions import ValidationError
from django.conf import settings as django_settings
from urllib.parse import urlparse

from eventyay.base.forms import SettingsForm
from eventyay.base.settings import validate_event_settings
from eventyay.base.models import Event
from eventyay.control.forms import (
     SplitDateTimeField,
     SplitDateTimePickerWidget,
     SlugWidget,
    )
from eventyay.base.forms import I18nModelForm
from eventyay.multidomain.models import KnownDomain


class EventCommonSettingsForm(SettingsForm):
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Event timezone'),
    )

    auto_fields = [
        "locales",
        "locale",
        "region",
        "contact_mail",
        "imprint_url",
        'logo_image',
        'logo_image_large',
        'event_logo_image',
        'logo_show_title',
        'og_image',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'theme_round_borders',
        'primary_font',
        'contact_mail',
        'imprint_url',
        'region',
        'frontpage_text',
    ]

    def clean(self):
        data = super().clean()
        settings_dict = self.event.settings.freeze()
        settings_dict.update(data)
        validate_event_settings(self.event, data)
        return data

    def __init__(self, *args, **kwargs):
        self.event = kwargs['obj']
        super().__init__(*args, **kwargs)


class EventUpdateForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        self.change_slug = kwargs.pop('change_slug', False)
        self.domain_field_enabled = kwargs.pop('domain', False)

        kwargs.setdefault('initial', {})
        self.instance = kwargs['instance']
        if self.domain_field_enabled and self.instance:
            initial_domain = self.instance.domains.first()
            if initial_domain:
                kwargs['initial'].setdefault('domain', initial_domain.domainname)

        super().__init__(*args, **kwargs)
        if self.instance and self.instance.organizer:
            self.fields['slug'].widget.organizer = self.instance.organizer
            self.fields['slug'].widget.event = self.instance

        if not self.change_slug:
            self.fields['slug'].widget.attrs['readonly'] = 'readonly'
        self.fields['location'].widget.attrs['rows'] = '3'
        self.fields['location'].widget.attrs['placeholder'] = _('Sample Conference Center\nHeidelberg, Germany')

        if self.domain_field_enabled:
            self.fields['domain'] = forms.CharField(
                max_length=255,
                label=_('Custom domain'),
                required=False,
                help_text=_('You need to configure the custom domain in the webserver beforehand.'),
            )

    def clean_domain(self):
        if not self.domain_field_enabled:
            return None
        d = self.cleaned_data.get('domain')
        if d:
            if d == urlparse(django_settings.SITE_URL).hostname:
                raise ValidationError(_('You cannot choose the base domain of this installation.'))
            if KnownDomain.objects.filter(domainname=d).exclude(event=self.instance.pk).exists():
                raise ValidationError(_('This domain is already in use for a different event or organizer.'))
        return d

    def save(self, commit=True):
        instance = super().save(commit)
        if self.domain_field_enabled and 'domain' in self.cleaned_data:
            current_domain = instance.domains.first()
            domain_value = self.cleaned_data['domain']
            if domain_value:
                if current_domain and current_domain.domainname != domain_value:
                    current_domain.delete()
                    KnownDomain.objects.create(
                        organizer=instance.organizer,
                        event=instance,
                        domainname=domain_value,
                    )
                elif not current_domain:
                    KnownDomain.objects.create(
                        organizer=instance.organizer,
                        event=instance,
                        domainname=domain_value,
                    )
            elif current_domain:
                current_domain.delete()
            instance.cache.clear()
        return instance

    def clean_slug(self):
        if self.change_slug:
            return self.cleaned_data['slug']
        return self.instance.slug

    class Meta:
        model = Event
        fields = [
            'name', 'slug', 'date_from', 'date_to', 'date_admission',
            'is_public', 'location', 'geo_lat', 'geo_lon',
        ]
        field_classes = {
            'date_from': SplitDateTimeField, 'date_to': SplitDateTimeField, 'date_admission': SplitDateTimeField,
        }
        widgets = {
            'slug': SlugWidget(attrs={'data-slug-source': 'name'}),
            'date_from': SplitDateTimePickerWidget(),
            'date_to': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_date_from_0'}),
            'date_admission': SplitDateTimePickerWidget(attrs={'data-date-default': '#id_date_from_0'}),
        }

