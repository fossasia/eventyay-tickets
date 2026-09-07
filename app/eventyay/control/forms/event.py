from decimal import Decimal
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import validate_email
from django.db.models import Q
from django.forms import CheckboxSelectMultiple, formset_factory
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.timezone import get_current_timezone_name
from django.utils.translation import gettext, pgettext_lazy
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_countries.fields import LazyTypedChoiceField
from i18nfield.forms import (
    I18nForm,
    I18nFormField,
    I18nFormSetMixin,
    I18nTextarea,
    I18nTextInput,
)
from zoneinfo import ZoneInfo
from eventyay.timezones import common_timezones, localize_datetime

from eventyay.base.channels import get_all_sales_channels
from eventyay.base.email import get_available_placeholders
from eventyay.base.forms import I18nModelForm, PlaceholderValidator, SettingsForm
from eventyay.base.meetup import (
    CAPACITY_LIMITED,
    CAPACITY_TYPE_CHOICES,
    CAPACITY_UNLIMITED,
    LOCATION_HYBRID,
    LOCATION_IN_PERSON,
    LOCATION_TYPE_CHOICES,
    LOCATION_VIRTUAL,
    PRIVACY_CHOICES,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    REGISTRATION_FEE_CHOICES,
    REGISTRATION_FEE_FREE,
    REGISTRATION_FEE_PAID,
    add_video_field_errors,
    build_video_form_fields,
    is_meetup_event,
)
from eventyay.control.forms.global_settings import StripeKeyValidator
from eventyay.consts import SizeKey
from eventyay.base.models import Event, Organizer, TaxRule, Team
from eventyay.base.models.event import EventMetaValue, SubEvent
from eventyay.base.reldate import RelativeDateField, RelativeDateTimeField
from eventyay.base.services.system_questions import (
    STATE_DEFAULT,
    STATE_DO_NOT_ASK,
    STATE_OPTIONAL,
    STATE_REQUIRED,
    SYSTEM_QUESTION_FIELD_SETTING_KEYS,
    get_system_question_base_state,
    get_system_question_field_overrides,
    get_system_question_product_overrides,
    set_system_question_field_overrides,
    state_to_asked_required,
)
from eventyay.base.settings import (
    EVENT_SERIES_CREATION_ENABLED,
    GlobalSettingsObject,
    PERSON_NAME_SCHEMES,
    PERSON_NAME_TITLE_GROUPS,
    validate_event_settings,
)
from eventyay.common.forms.fields import ImageField
from eventyay.common.forms.widgets import EnhancedSelect, HtmlDateInput, HtmlDateTimeInput
from eventyay.common.language import get_language_choices_native_with_ui_name
from eventyay.common.text.phrases import phrases
from eventyay.control.forms import (
    ExtFileField,
    MultipleLanguagesWidget,
    SlugWidget,
    SplitDateTimeField,
    SplitDateTimePickerWidget,
)
from eventyay.control.forms.widgets import Select2
from eventyay.helpers.countries import CachedCountries
from eventyay.multidomain.urlreverse import build_absolute_uri
from eventyay.orga.forms.widgets import HeaderSelect
from eventyay.plugins.banktransfer.payment import BankTransfer


# Shared constants for require_registered_account_for_tickets field
REQUIRE_REGISTERED_ACCOUNT_LABEL = _('Only allow registered accounts to get a ticket')
REQUIRE_REGISTERED_ACCOUNT_HELP_TEXT = _(
    'If this option is turned on, users must be logged in before completing an order. '
    'When a user clicks "Checkout" without being logged in, they will be redirected to the login page. '
    'The "Continue as a Guest" option will not be available for attendees in this event.'
)


ORGANIZER_EMAIL_MODEL_DEFAULT = Event._meta.get_field('email').default
ORGANIZER_EMAIL_PLACEHOLDER = _('name@example.org')


def apply_organizer_email_placeholder(field):
    field.widget.attrs['placeholder'] = ORGANIZER_EMAIL_PLACEHOLDER


def get_default_organizer_email() -> str:
    default_email = GlobalSettingsObject().settings.mail_from or settings.DEFAULT_FROM_EMAIL
    return str(default_email or ORGANIZER_EMAIL_MODEL_DEFAULT).strip()


def normalize_organizer_email_initial(email) -> str:
    cleaned_email = str(email or '').strip()
    if cleaned_email in {get_default_organizer_email(), ORGANIZER_EMAIL_MODEL_DEFAULT}:
        return ''
    return cleaned_email


class EventWizardFoundationForm(forms.Form):
    locales = forms.MultipleChoiceField(
        choices=settings.LANGUAGES,
        label=_('Event languages'),
        widget=MultipleLanguagesWidget,
        help_text=_(
            "Users will be able to use eventyay in these languages, and you will be able to provide all texts in "
            "these languages. Drag and drop selected languages to reorder them — the first language (bold border) "
            "is used as your event's default language."
        ),
    )
    has_subevents = forms.BooleanField(
        label=_('This is an event series'),
        required=False,
    )
    is_video_creation = forms.BooleanField(
        label=_('Create Video platform for this Event.'),
        help_text=_('This will create a new Video platform for this event.'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.session = kwargs.pop('session')
        super().__init__(*args, **kwargs)
        localized_language_choices = get_language_choices_native_with_ui_name()
        self.fields['locales'].choices = localized_language_choices
        qs = Organizer.objects.all()
        if not self.user.has_active_staff_session(self.session.session_key):
            qs = qs.filter(id__in=self.user.teams.filter(can_create_events=True).values_list('organizer', flat=True))
        # Make organizer required only if more than one exists
        organizer_count = qs.count()
        is_required = organizer_count > 1

        select2_url = reverse('control:organizers.select2') + '?can_create=1'

        self.fields['organizer'] = forms.ModelChoiceField(
            label=_('Organizer'),
            queryset=qs,
            widget=Select2(
                attrs={
                    'data-model-select2': 'generic',
                    'data-select2-url': select2_url,
                    'data-placeholder': _('Organizer'),
                }
            ),
            empty_label=_('Organizer') if is_required else None,
            required=is_required,
        )
        self.fields['organizer'].widget.choices = self.fields['organizer'].choices

        # Auto-select if only one organizer exists or user has default organizer
        if 'organizer' not in self.initial:
            if organizer_count == 1:
                self.fields['organizer'].initial = qs.first()
                self.fields['organizer'].required = False
            elif self.user and self.user.is_authenticated:
                default_org = self.user.get_default_organizer(can_create_events=True)
                if default_org and qs.filter(pk=default_org.pk).exists():
                    self.fields['organizer'].initial = default_org

    def clean(self):
        cleaned_data = super().clean()
        locales = cleaned_data.get('locales', [])

        gs = GlobalSettingsObject()
        series_enabled = gs.settings.get(EVENT_SERIES_CREATION_ENABLED, as_type=bool, default=True)
        if not series_enabled and cleaned_data.get('has_subevents'):
            raise ValidationError({
                'has_subevents': _('Event series creation is disabled by the administrator.')
            })

        return cleaned_data


class EventWizardBasicsForm(I18nModelForm):
    error_messages = {
        'duplicate_slug': _('This short name is already taken by another event. '
                            'Please choose a different one or use the "Set to random" button '
                            'for an automatic suggestion.'),
    }
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Event timezone'),
    )
    locale = forms.ChoiceField(
        choices=settings.LANGUAGES,
        label=_('Default language'),
        required=False,
    )
    tax_rate = forms.DecimalField(
        label=_('Sales tax rate'),
        help_text=_(
            'Do you need to pay sales tax on your tickets? In this case, please enter the applicable tax rate '
            'here in percent. If you have a more complicated tax situation, you can add more tax rates and '
            'detailed configuration later.'
        ),
        required=False,
        min_value=0,
        max_value=100,
    )
    team = forms.ModelChoiceField(
        label=_('Grant access to team'),
        help_text=_(
            'You are allowed to create events under this organizer, however you do not have permission '
            'to edit all events under this organizer. Please select one of your existing teams that will'
            ' be granted access to this event.'
        ),
        queryset=Team.objects.none(),
        required=False,
        empty_label=_('Create a new team for this event with me as the only member'),
    )

    class Meta:
        model = Event
        fields = [
            'name',
            'slug',
            'date_from',
            'date_to',
            'presale_start',
            'presale_end',
            'location',
            'geo_lat',
            'geo_lon',
        ]
        field_classes = {
            'date_from': SplitDateTimeField,
            'date_to': SplitDateTimeField,
            'presale_start': SplitDateTimeField,
            'presale_end': SplitDateTimeField,
        }
        widgets = {
            'date_from': SplitDateTimePickerWidget(),
            'date_to': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_basics-date_from_0'}),
            'presale_start': SplitDateTimePickerWidget(),
            'presale_end': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_basics-presale_start_0'}),
            'slug': SlugWidget,
        }

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer')
        self.locales = kwargs.get('locales')
        self.has_subevents = kwargs.pop('has_subevents')
        self.is_video_creation = kwargs.pop('is_video_creation')
        self.user = kwargs.pop('user')
        self.restrict_locale_choices = kwargs.pop('restrict_locale_choices', True)
        kwargs.pop('session')
        kwargs.pop('content_locales', None)
        super().__init__(*args, **kwargs)
        if 'timezone' not in self.initial:
            self.initial['timezone'] = get_current_timezone_name()
        if self.restrict_locale_choices:
            self.fields['locale'].choices = [(a, b) for a, b in settings.LANGUAGES if a in self.locales]
        else:
            self.fields['locale'].choices = settings.LANGUAGES
        self.fields['location'].widget.attrs['rows'] = '3'
        self.fields['location'].widget.attrs['placeholder'] = _('Sample Conference Center\nHeidelberg, Germany')
        self.fields['geo_lat'].widget.attrs['placeholder'] = _('Latitude, e.g. 40.7128')
        self.fields['geo_lon'].widget.attrs['placeholder'] = _('Longitude, e.g. -74.0060')
        self.fields['slug'].widget.prefix = build_absolute_uri(self.organizer, 'presale:organizer.index')
        self.fields['slug'].widget.attrs.setdefault('class', 'form-control')

        # Generate a unique slug if none provided
        if not self.initial.get('slug'):
            charset = list('abcdefghjklmnpqrstuvwxyz3789')

            # Try different lengths until we find a unique slug
            length = 6
            counter = 0
            while not self.initial.get('slug'):
                if length <= 10:
                    candidate = get_random_string(length=length, allowed_chars=charset)
                    length += 1
                else:
                    # Fallback: add counter to ensure uniqueness
                    candidate = f'{get_random_string(length=4, allowed_chars=charset)}{counter}'
                    counter += 1

                if not self.organizer.events.filter(slug__iexact=candidate).exists():
                    self.initial['slug'] = candidate
                    break

        if self.has_subevents:
            del self.fields['presale_start']
            del self.fields['presale_end']
            del self.fields['date_to']

        if self.has_control_rights(self.user, self.organizer):
            del self.fields['team']
        else:
            self.fields['team'].queryset = self.user.teams.filter(organizer=self.organizer)
            if not self.organizer.settings.get('event_team_provisioning', True, as_type=bool):
                self.fields['team'].required = True
                self.fields['team'].empty_label = None
                self.fields['team'].initial = 0

    def clean(self):
        data = super().clean()
        if not data.get('locale') and self.locales:
            data['locale'] = self.locales[0]
        if data.get('locale') not in self.locales:
            if self.locales:
                data['locale'] = self.locales[0]
            else:
                raise ValidationError(
                    {'locale': _('Your default locale must also be enabled for your event (see box above).')}
                )
        if data.get('timezone') not in common_timezones:
            raise ValidationError({'timezone': _('Your default locale must be specified.')})

        # change timezone
        zone = ZoneInfo(data.get('timezone'))
        data['date_from'] = self.reset_timezone(zone, data.get('date_from'))
        data['date_to'] = self.reset_timezone(zone, data.get('date_to'))
        data['presale_start'] = self.reset_timezone(zone, data.get('presale_start'))
        data['presale_end'] = self.reset_timezone(zone, data.get('presale_end'))
        return data

    @staticmethod
    def reset_timezone(zone, dt):
        return localize_datetime(dt, zone)

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Event.objects.filter(slug__iexact=slug, organizer=self.organizer).exists():
            raise forms.ValidationError(self.error_messages['duplicate_slug'], code='duplicate_slug')
        return slug.lower()


    @staticmethod
    def has_control_rights(user, organizer):
        return (
            user.teams.filter(
                organizer=organizer,
                all_events=True,
                can_change_event_settings=True,
                can_change_items=True,
                can_change_orders=True,
                can_change_vouchers=True,
            ).exists()
            or user.is_staff
        )


class EventChoiceMixin:
    def label_from_instance(self, obj):
        return mark_safe(
            '{}<br /><span class="text-muted">{} · {}</span>'.format(
                escape(str(obj)),
                (obj.get_date_range_display() if not obj.has_subevents else _('Event series')),
                obj.slug,
            )
        )


class EventChoiceField(forms.ModelChoiceField):
    pass


class SafeEventMultipleChoiceField(EventChoiceMixin, forms.ModelMultipleChoiceField):
    def __init__(self, queryset, *args, **kwargs):
        queryset = queryset.model.objects.none()
        super().__init__(queryset, *args, **kwargs)


class EventWizardCopyForm(forms.Form):
    @staticmethod
    def copy_from_queryset(user, session):
        if user.has_active_staff_session(session.session_key):
            return Event.objects.all()
        return Event.objects.filter(
            Q(
                organizer_id__in=user.teams.filter(
                    all_events=True,
                    can_change_event_settings=True,
                    can_change_items=True,
                ).values_list('organizer', flat=True)
            )
            | Q(
                id__in=user.teams.filter(can_change_event_settings=True, can_change_items=True).values_list(
                    'limit_events__id', flat=True
                )
            )
        )

    def __init__(self, *args, **kwargs):
        kwargs.pop('organizer')
        kwargs.pop('locales')
        self.session = kwargs.pop('session')
        kwargs.pop('has_subevents')
        self.user = kwargs.pop('user')
        kwargs.pop('is_video_creation')
        super().__init__(*args, **kwargs)

        self.fields['copy_from_event'] = EventChoiceField(
            label=_('Copy configuration from'),
            queryset=EventWizardCopyForm.copy_from_queryset(self.user, self.session),
            widget=Select2(
                attrs={
                    'data-model-select2': 'event',
                    'data-select2-url': reverse('control:events.typeahead') + '?can_copy=1',
                    'data-placeholder': _('Do not copy'),
                }
            ),
            empty_label=_('Do not copy'),
            required=False,
        )
        self.fields['copy_from_event'].widget.choices = self.fields['copy_from_event'].choices


class EventWizardDisplayForm(forms.Form):
    header_pattern = forms.ChoiceField(
        label=phrases.orga.event_header_pattern_label,
        help_text=phrases.orga.event_header_pattern_help_text,
        choices=Event.HEADER_PATTERN_CHOICES,
        required=False,
        widget=HeaderSelect,
    )
    email = forms.EmailField(
        label=_('Organizer email address'),
        help_text=_("Attendees can reach you through a contact form. Messages will be forwarded to this address."),
        required=False,
    )

    def __init__(self, *args, user=None, locales=None, organizer=None, **kwargs):
        super().__init__(*args, **kwargs)
        logo = Event._meta.get_field('logo')
        self.fields['logo'] = ImageField(required=False, label=logo.verbose_name, help_text=logo.help_text)


class EventWizardInitialForm(forms.Form):
    locales = forms.MultipleChoiceField(
        choices=settings.LANGUAGES,
        label=_('Use languages'),
        help_text=_('Choose all languages that your event should be available in.'),
        widget=MultipleLanguagesWidget,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organizer'] = forms.ModelChoiceField(
            label=_('Organizer'),
            queryset=(
                Organizer.objects.filter(
                    id__in=user.teams.filter(can_create_events=True).values_list('organizer', flat=True)
                )
                if not user.is_administrator
                else Organizer.objects.all()
            ),
            widget=EnhancedSelect,
            empty_label=None,
            required=True,
            help_text=_(
                'The organizer running the event can copy settings from previous events and '
                'share team permissions across all or multiple events.'
            ),
        )
        self.fields['organizer'].initial = self.fields['organizer'].queryset.first()


class EventWizardTimelineForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        required=False,
        help_text=_(
            'The default deadline for your Call for Papers. You can assign additional deadlines to '
            'individual session types, which will take precedence over this deadline.'
        ),
        widget=HtmlDateTimeInput,
    )

    def __init__(self, *args, user=None, locales=None, organizer=None, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        if date_from and date_to and date_from > date_to:
            error = forms.ValidationError(phrases.orga.event_date_start_invalid)
            self.add_error('date_from', error)
        return data

    class Meta:
        model = Event
        fields = ('date_from', 'date_to')
        widgets = {
            'date_from': HtmlDateInput,
            'date_to': HtmlDateInput,
        }


class EventMetaValueForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.property = kwargs.pop('property')
        self.disabled = kwargs.pop('disabled')
        super().__init__(*args, **kwargs)
        if self.property.allowed_values:
            self.fields['value'] = forms.ChoiceField(
                label=self.property.name,
                choices=[
                    (
                        '',
                        (_('Default ({value})').format(value=self.property.default) if self.property.default else ''),
                    ),
                ]
                + [(a.strip(), a.strip()) for a in self.property.allowed_values.splitlines()],
            )
        else:
            self.fields['value'].label = self.property.name
            self.fields['value'].widget.attrs['placeholder'] = self.property.default
            self.fields['value'].widget.attrs['data-typeahead-url'] = (
                reverse('control:events.meta.typeahead')
                + '?'
                + urlencode(
                    {
                        'property': self.property.name,
                        'organizer': self.property.organizer.slug,
                    }
                )
            )
        self.fields['value'].required = False
        if self.disabled:
            self.fields['value'].widget.attrs['readonly'] = 'readonly'

    def clean_slug(self):
        if self.disabled:
            return self.instance.value if self.instance else None
        return self.cleaned_data['slug']

    class Meta:
        model = EventMetaValue
        fields = ['value']
        widgets = {'value': forms.TextInput()}


class EventUpdateForm(I18nModelForm):
    def __init__(self, *args, **kwargs):

        kwargs.setdefault('initial', {})
        self.instance = kwargs['instance']
        super().__init__(*args, **kwargs)
        self.fields['sales_channels'] = forms.MultipleChoiceField(
            label=self.fields['sales_channels'].label,
            help_text=self.fields['sales_channels'].help_text,
            required=self.fields['sales_channels'].required,
            initial=self.fields['sales_channels'].initial,
            choices=((c.identifier, c.verbose_name) for c in get_all_sales_channels().values()),
            widget=forms.CheckboxSelectMultiple,
        )

    def save(self, commit=True):
        instance = super().save(commit)

        return instance

    def clean_slug(self):
        return self.instance.slug

    class Meta:
        model = Event
        localized_fields = '__all__'
        fields = [
            'currency',
            'presale_start',
            'presale_end',
            'sales_channels',
        ]
        field_classes = {
            'presale_start': SplitDateTimeField,
            'presale_end': SplitDateTimeField,
        }
        widgets = {
            'presale_start': SplitDateTimePickerWidget(),
            'presale_end': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_presale_start_0'}),
            'sales_channels': CheckboxSelectMultiple(),
        }


class EventSettingsForm(SettingsForm):
    name_scheme = forms.ChoiceField(
        label=_('Name format'),
        help_text=_(
            'This defines how eventyay will ask for human names. Changing this after you already received '
            'orders might lead to unexpected behavior when sorting or changing names.'
        ),
        required=True,
    )
    name_scheme_titles = forms.ChoiceField(
        label=_('Allowed titles'),
        help_text=_(
            'If the naming scheme you defined above allows users to input a title, you can use this to '
            'restrict the set of selectable titles.'
        ),
        required=False,
    )

    auto_fields = [
        'presale_has_ended_text',
        'voucher_explanation_text',
        'checkout_success_text',
        'show_products_outside_presale_period',
        'display_net_prices',
        'presale_start_show_date',
        'show_quota_left',
        'waiting_list_enabled',
        'waiting_list_hours',
        'waiting_list_auto',
        'waiting_list_names_asked',
        'waiting_list_names_required',
        'waiting_list_phones_asked',
        'waiting_list_phones_required',
        'waiting_list_phones_explanation_text',
        'show_variations_expanded',
        'hide_sold_out',
        'redirect_to_checkout_directly',
        'frontpage_subevent_ordering',
        'event_list_type',
        'event_list_available_only',
        'frontpage_text',
        'event_info_text',
        'require_registered_account_for_tickets',
        'attendee_names_asked',
        'attendee_names_required',
        'attendee_emails_asked',
        'attendee_emails_required',
        'attendee_company_asked',
        'attendee_company_required',
        'attendee_job_title_asked',
        'attendee_job_title_required',
        'attendee_addresses_asked',
        'attendee_addresses_required',
        'attendee_data_explanation_text',
        'order_phone_asked',
        'order_phone_required',
        'banner_text',
        'banner_text_bottom',
        'order_email_asked',
        'order_email_required',
        'order_email_asked_twice',
        'include_wikimedia_username',
        'allow_modifications',
        'last_order_modification_date',
        'allow_modifications_after_checkin',
        'primary_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'theme_round_borders',
        'hover_button_color',
        'video_navigation_background_color',
        'video_sidebar_text_color',
        'video_sidebar_hover_color',
        'primary_font',
        'logo_image',
        'logo_image_large',
        'event_logo_image',
        'event_preview_image',
        'logo_show_title',
        'og_image',
        'menu_label_tickets',
        'menu_label_join_video',
    ]

    def clean(self):
        data = super().clean()
        settings_dict = self.event.settings.freeze()
        settings_dict.update(data)

        # set all dependants of virtual_keys and
        # delete all virtual_fields to prevent them from being saved
        for virtual_key in self.virtual_keys:
            if virtual_key not in data:
                continue
            base_key = virtual_key.rsplit('_', 2)[0]
            asked_key = base_key + '_asked'
            required_key = base_key + '_required'

            if data[virtual_key] == 'optional':
                data[asked_key] = True
                data[required_key] = False
            elif data[virtual_key] == 'required':
                data[asked_key] = True
                data[required_key] = True
            # Explicitly check for 'do_not_ask'.
            # Do not overwrite as default-behaviour when no value for virtual field is transmitted!
            # Note: Only set asked to False, preserve the existing required value
            elif data[virtual_key] == 'do_not_ask':
                data[asked_key] = False
                # Don't touch required_key - preserve existing required state

            # hierarkey.forms cannot handle non-existent keys in cleaned_data => do not delete, but set to None
            data[virtual_key] = None

        validate_event_settings(self.event, data)
        return data

    def __init__(self, *args, **kwargs):
        self.event = kwargs['obj']
        super().__init__(*args, **kwargs)
        self.fields['name_scheme'].choices = (
            (
                k,
                _('Ask for {fields}, display like {example}').format(
                    fields=' + '.join(str(vv[1]) for vv in v['fields']),
                    example=v['concatenation'](v['sample']),
                ),
            )
            for k, v in PERSON_NAME_SCHEMES.items()
        )
        self.fields['name_scheme_titles'].choices = [('', _('Free text input'))] + [
            (k, '{scheme}: {samples}'.format(scheme=v[0], samples=', '.join(v[1])))
            for k, v in PERSON_NAME_TITLE_GROUPS.items()
        ]
        if not self.event.has_subevents:
            self.fields.pop('frontpage_subevent_ordering', None)
            self.fields.pop('event_list_type', None)
            self.fields.pop('event_list_available_only', None)

        # create "virtual" fields for better UX when editing <name>_asked and <name>_required fields
        self.virtual_keys = []
        for asked_key in [key for key in self.fields.keys() if key.endswith('_asked')]:
            required_key = asked_key.rsplit('_', 1)[0] + '_required'
            virtual_key = asked_key + '_required'
            if required_key not in self.fields or virtual_key in self.fields:
                # either no matching required key or
                # there already is a field with virtual_key defined manually, so do not overwrite
                continue

            asked_field = self.fields[asked_key]

            self.fields[virtual_key] = forms.ChoiceField(
                label=asked_field.label,
                help_text=asked_field.help_text,
                required=False,
                widget=forms.RadioSelect,
                choices=[
                    # default key needs a value other than '' because with '' it would also overwrite
                    # even if combi-field is not transmitted
                    ('do_not_ask', _('Do not ask')),
                    ('optional', _('Ask, but do not require input')),
                    ('required', _('Ask and require input')),
                ],
            )
            self.virtual_keys.append(virtual_key)

            if self.initial.get(required_key):
                self.initial[virtual_key] = "required"
            elif self.initial.get(asked_key):
                self.initial[virtual_key] = "optional"
            else:
                self.initial[virtual_key] = 'do_not_ask'


class GeneralEventSettingsForm(EventSettingsForm):
    """
    Settings form used on the general event settings page.

    Keep this list limited to fields rendered there so saving that page
    cannot overwrite dedicated order-form settings.
    """

    auto_fields = [
        'presale_has_ended_text',
        'voucher_explanation_text',
        'checkout_success_text',
        'show_products_outside_presale_period',
        'display_net_prices',
        'presale_start_show_date',
        'show_quota_left',
        'waiting_list_enabled',
        'waiting_list_hours',
        'waiting_list_auto',
        'waiting_list_names_asked',
        'waiting_list_names_required',
        'waiting_list_phones_asked',
        'waiting_list_phones_required',
        'waiting_list_phones_explanation_text',
        'show_variations_expanded',
        'hide_sold_out',
        'redirect_to_checkout_directly',
        'frontpage_subevent_ordering',
        'event_list_type',
        'event_list_available_only',
        'event_info_text',
        'banner_text',
        'banner_text_bottom',
        'allow_modifications',
        'last_order_modification_date',
        'allow_modifications_after_checkin',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('name_scheme', None)
        self.fields.pop('name_scheme_titles', None)


class OrderFormSettingsForm(EventSettingsForm):
    """
    Settings form used on the dedicated order-forms page.

    Keep this list limited to fields rendered there so saving that page
    cannot overwrite unrelated event settings.
    """

    auto_fields = [
        'attendee_names_asked',
        'attendee_names_required',
        'attendee_emails_asked',
        'attendee_emails_required',
        'attendee_company_asked',
        'attendee_company_required',
        'attendee_job_title_asked',
        'attendee_job_title_required',
        'attendee_addresses_asked',
        'attendee_addresses_required',
        'attendee_data_explanation_text',
        'order_phone_asked',
        'order_phone_required',
        'order_email_asked',
        'order_email_required',
        'order_email_asked_twice',
        'require_registered_account_for_tickets',
        'include_wikimedia_username',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('name_scheme', None)
        self.fields.pop('name_scheme_titles', None)

    def save(self):
        fields_with_cleared_overrides = set()
        for field_id in SYSTEM_QUESTION_FIELD_SETTING_KEYS:
            clear_override_key = self.add_prefix(f'clear_override_{field_id}')
            if self.data.get(clear_override_key) == '1':
                fields_with_cleared_overrides.add(field_id)

        result = super().save()

        for field_id in fields_with_cleared_overrides:
            set_system_question_field_overrides(self.obj, field_id, {})

        return result


class OrderFormCustomerFieldSettingsForm(SettingsForm):
    FIELD_LABELS = {
        'order_email': _('E-mail'),
        'order_phone': _('Phone number'),
    }

    def __init__(self, *args, **kwargs):
        self.field_id = kwargs.pop('field_id', None)
        
        if self.field_id == 'order_email':
            self.auto_fields = [
                'order_email_asked_twice',
                'checkout_email_helptext',
            ]
        elif self.field_id == 'order_phone':
            self.auto_fields = [
                'checkout_phone_helptext',
            ]
        else:
            self.auto_fields = []
            
        super().__init__(*args, **kwargs)


class OrderFormDefaultFieldSettingsForm(forms.Form):
    FIELD_LABELS = {
        'attendee_name_parts': _('Attendee names'),
        'attendee_email': _('Attendee emails'),
        'company': _('Company'),
        'job_title': _('Job title'),
        'street': _('Postal addresses'),
    }

    global_state = forms.ChoiceField(
        label=_('Default behavior'),
        help_text=_(
            'Used for all admission products unless a product-specific override is configured below.'
        ),
        choices=[
            (STATE_DO_NOT_ASK, _('Do not ask')),
            (STATE_OPTIONAL, _('Ask, but do not require input')),
            (STATE_REQUIRED, _('Ask and require input')),
        ],
        widget=forms.RadioSelect,
    )
    name_scheme = forms.ChoiceField(
        label=_('Name format'),
        help_text=_(
            'This defines how eventyay will ask for human names. Changing this after you already received '
            'orders might lead to unexpected behavior when sorting or changing names.'
        ),
        required=True,
    )
    name_scheme_titles = forms.ChoiceField(
        label=_('Allowed titles'),
        help_text=_(
            'If the naming scheme you defined above allows users to input a title, you can use this to '
            'restrict the set of selectable titles.'
        ),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        self.field_id = kwargs.pop('field_id')
        self.products = list(self.event.products.filter(admission=True).order_by('position', 'id'))
        self.product_field_names = []
        super().__init__(*args, **kwargs)

        self.fields['global_state'].initial = get_system_question_base_state(self.event, self.field_id)

        state_choices = [
            (STATE_DEFAULT, _('Use default setting')),
            (STATE_DO_NOT_ASK, _('Do not ask')),
            (STATE_OPTIONAL, _('Ask, but do not require input')),
            (STATE_REQUIRED, _('Ask and require input')),
        ]
        overrides = get_system_question_field_overrides(self.event, self.field_id)

        for product in self.products:
            field_name = self._product_field_name(product.pk)
            self.fields[field_name] = forms.ChoiceField(
                label=str(product),
                choices=state_choices,
                required=True,
                widget=forms.Select,
            )
            self.initial[field_name] = overrides.get(str(product.pk), STATE_DEFAULT)
            self.product_field_names.append(field_name)

        if self.field_id == 'attendee_name_parts':
            self.fields['name_scheme'].choices = [
                (
                    k,
                    _('Ask for {fields}, display like {example}').format(
                        fields=' + '.join(str(vv[1]) for vv in v['fields']),
                        example=v['concatenation'](v['sample']),
                    ),
                )
                for k, v in PERSON_NAME_SCHEMES.items()
            ]
            self.fields['name_scheme_titles'].choices = [('', _('Free text input'))] + [
                (k, '{scheme}: {samples}'.format(scheme=v[0], samples=', '.join(v[1])))
                for k, v in PERSON_NAME_TITLE_GROUPS.items()
            ]
            self.fields['name_scheme'].initial = self.event.settings.name_scheme
            self.fields['name_scheme_titles'].initial = self.event.settings.name_scheme_titles
        else:
            self.fields.pop('name_scheme')
            self.fields.pop('name_scheme_titles')

    @staticmethod
    def _product_field_name(product_id: int) -> str:
        return f'product_{product_id}'

    def clean_name_scheme(self) -> str:
        value = self.cleaned_data['name_scheme']
        if value not in PERSON_NAME_SCHEMES:
            raise forms.ValidationError(_('Please select a valid name format.'))
        return value

    def save(self) -> dict:
        asked_key, required_key = SYSTEM_QUESTION_FIELD_SETTING_KEYS[self.field_id]
        global_state = self.cleaned_data['global_state']
        asked, required = state_to_asked_required(global_state)
        if global_state == STATE_DO_NOT_ASK:
            required = self.event.settings.get(required_key, as_type=bool)

        settings_dict = self.event.settings.freeze()
        settings_dict[asked_key] = asked
        settings_dict[required_key] = required
        if self.field_id == 'attendee_name_parts':
            settings_dict['name_scheme'] = self.cleaned_data['name_scheme']
            settings_dict['name_scheme_titles'] = self.cleaned_data['name_scheme_titles']
        validate_event_settings(self.event, settings_dict)

        self.event.settings.set(asked_key, asked)
        self.event.settings.set(required_key, required)

        product_states = {}
        for product in self.products:
            state = self.cleaned_data[self._product_field_name(product.pk)]
            if state != STATE_DEFAULT:
                product_states[str(product.pk)] = state
        set_system_question_field_overrides(self.event, self.field_id, product_states)

        if self.field_id == 'attendee_name_parts':
            self.event.settings.name_scheme = self.cleaned_data['name_scheme']
            self.event.settings.name_scheme_titles = self.cleaned_data['name_scheme_titles']

        return {
            asked_key: asked,
            required_key: required,
            'system_question_product_overrides': get_system_question_product_overrides(self.event),
            **(
                {
                    'name_scheme': self.cleaned_data['name_scheme'],
                    'name_scheme_titles': self.cleaned_data['name_scheme_titles'],
                }
                if self.field_id == 'attendee_name_parts'
                else {}
            ),
        }


class CancelSettingsForm(SettingsForm):
    auto_fields = [
        'cancel_allow_user',
        'cancel_allow_user_until',
        'cancel_allow_user_paid',
        'cancel_allow_user_paid_until',
        'cancel_allow_user_paid_keep',
        'cancel_allow_user_paid_keep_fees',
        'cancel_allow_user_paid_keep_percentage',
        'cancel_allow_user_paid_adjust_fees',
        'cancel_allow_user_paid_adjust_fees_explanation',
        'cancel_allow_user_paid_adjust_fees_step',
        'cancel_allow_user_paid_refund_as_giftcard',
        'cancel_allow_user_paid_require_approval',
        'change_allow_user_price',
        'change_allow_user_until',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.obj.settings.giftcard_expiry_years is not None:
            self.fields['cancel_allow_user_paid_refund_as_giftcard'].help_text = gettext(
                'You have configured gift cards to be valid {} years plus the year the gift card is issued in.'
            ).format(self.obj.settings.giftcard_expiry_years)


class PaymentSettingsForm(SettingsForm):
    auto_fields = [
        'payment_term_mode',
        'payment_term_days',
        'payment_term_weekdays',
        'payment_term_minutes',
        'payment_term_last',
        'payment_term_expire_automatically',
        'payment_term_accept_late',
        'payment_pending_hidden',
        'payment_explanation',
    ]
    tax_rate_default = forms.ModelChoiceField(
        queryset=TaxRule.objects.none(),
        label=_('Tax rule for payment fees'),
        required=False,
        help_text=_(
            'The tax rule that applies for additional fees you configured for single payment methods. This '
            'will set the tax rate and reverse charge rules, other settings of the tax rule are ignored.'
        ),
    )

    def clean_payment_term_days(self):
        value = self.cleaned_data.get('payment_term_days')
        if self.cleaned_data.get('payment_term_mode') == 'days' and value is None:
            raise ValidationError(_('This field is required.'))
        return value

    def clean_payment_term_minutes(self):
        value = self.cleaned_data.get('payment_term_minutes')
        if self.cleaned_data.get('payment_term_mode') == 'minutes' and value is None:
            raise ValidationError(_('This field is required.'))
        return value

    def clean(self):
        data = super().clean()
        settings_dict = self.obj.settings.freeze()
        settings_dict.update(data)
        validate_event_settings(self.obj, data)
        return data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tax_rate_default'].queryset = self.obj.tax_rules.all()


class ProviderForm(SettingsForm):
    """
    This is a SettingsForm, but if fields are set to required=True, validation
    errors are only raised if the payment method is enabled.
    """

    def __init__(self, *args, **kwargs):
        self.settingspref = kwargs.pop('settingspref')
        self.provider = kwargs.pop('provider', None)
        super().__init__(*args, **kwargs)

    def prepare_fields(self):
        for k, v in self.fields.items():
            v._required = v.required
            v.required = False
            v.widget.is_required = False
            if isinstance(v, I18nFormField):
                v._required = v.one_required
                v.one_required = False
                v.widget.enabled_locales = self.locales
            elif isinstance(v, (RelativeDateTimeField, RelativeDateField)):
                v.set_event(self.obj)

            if hasattr(v, '_as_type'):
                self.initial[k] = self.obj.settings.get(k, as_type=v._as_type, default=v.initial)

    def clean(self):
        cleaned_data = super().clean()
        enabled = cleaned_data.get(self.settingspref + '_enabled')
        if not enabled:
            return
        if cleaned_data.get(self.settingspref + '_hidden_url', None):
            cleaned_data[self.settingspref + '_hidden_url'] = None
        for k, v in self.fields.items():
            val = cleaned_data.get(k)
            if v._required and not val:
                self.add_error(k, _('This field is required.'))
        if self.provider:
            cleaned_data = self.provider.settings_form_clean(cleaned_data)
        return cleaned_data


class InvoiceSettingsForm(SettingsForm):
    auto_fields = [
        'invoice_address_asked',
        'invoice_address_required',
        'invoice_address_vatid',
        'invoice_address_company_required',
        'invoice_address_beneficiary',
        'invoice_address_custom_field',
        'invoice_name_required',
        'invoice_address_not_asked_free',
        'invoice_include_free',
        'invoice_show_payments',
        'invoice_reissue_after_modify',
        'invoice_generate',
        'invoice_attendee_name',
        'invoice_include_expire_date',
        'invoice_numbers_consecutive',
        'invoice_numbers_prefix',
        'invoice_numbers_prefix_cancellations',
        'invoice_numbers_counter_length',
        'invoice_address_explanation_text',
        'invoice_email_attachment',
        'invoice_address_from_name',
        'invoice_address_from',
        'invoice_address_from_zipcode',
        'invoice_address_from_city',
        'invoice_address_from_country',
        'invoice_address_from_tax_id',
        'invoice_address_from_vat_id',
        'invoice_introductory_text',
        'invoice_additional_text',
        'invoice_footer_text',
        'invoice_eu_currencies',
    ]

    invoice_generate_sales_channels = forms.MultipleChoiceField(
        label=_('Generate invoices for Sales channels'),
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        help_text=_(
            'If you have enabled invoice generation in the previous setting, you can limit it here to specific '
            'sales channels.'
        ),
    )
    invoice_renderer = forms.ChoiceField(label=_('Invoice style'), required=True, choices=[])
    invoice_language = forms.ChoiceField(
        widget=forms.Select,
        required=True,
        label=_('Invoice language'),
        choices=[('__user__', _("The user's language"))] + settings.LANGUAGES,
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        self.fields['invoice_renderer'].choices = [
            (r.identifier, r.verbose_name) for r in event.get_invoice_renderers().values()
        ]
        self.fields['invoice_numbers_prefix'].widget.attrs['placeholder'] = event.slug.upper() + '-'
        if event.settings.invoice_numbers_prefix:
            self.fields['invoice_numbers_prefix_cancellations'].widget.attrs['placeholder'] = (
                event.settings.invoice_numbers_prefix
            )
        else:
            self.fields['invoice_numbers_prefix_cancellations'].widget.attrs['placeholder'] = event.slug.upper() + '-'
        locale_names = dict(settings.LANGUAGES)
        self.fields['invoice_language'].choices = [('__user__', _("The user's language"))] + [
            (a, locale_names[a]) for a in event.settings.locales
        ]
        self.fields['invoice_generate_sales_channels'].choices = (
            (c.identifier, c.verbose_name) for c in get_all_sales_channels().values()
        )

    def clean(self):
        data = super().clean()
        settings_dict = self.obj.settings.freeze()
        settings_dict.update(data)
        validate_event_settings(self.obj, data)
        return data


def multimail_validate(val):
    s = val.split(',')
    for part in s:
        validate_email(part.strip())
    return s


def contains_web_channel_validate(val):
    if 'web' not in val:
        raise ValidationError(_('The online shop must be selected to receive these emails.'))


class MailSettingsForm(SettingsForm):
    auto_fields = [
        'mail_prefix',
        'mail_from',
        'mail_reply_to',
        'mail_from_name',
        'mail_attach_ical',
        'mail_attach_tickets',
    ]

    mail_sales_channel_placed_paid = forms.MultipleChoiceField(
        choices=lambda: [(ident, sc.verbose_name) for ident, sc in get_all_sales_channels().items()],
        label=_('Sales channels for checkout emails'),
        help_text=_(
            'The order placed and paid emails will only be send to orders from these sales channels. '
            'The online shop must be enabled.'
        ),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
        validators=[contains_web_channel_validate],
    )

    mail_sales_channel_download_reminder = forms.MultipleChoiceField(
        choices=lambda: [(ident, sc.verbose_name) for ident, sc in get_all_sales_channels().items()],
        label=_('Sales channels'),
        help_text=_(
            'This email will only be send to orders from these sales channels. The online shop must be enabled.'
        ),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
        validators=[contains_web_channel_validate],
    )

    mail_bcc = forms.CharField(
        label=_('Bcc address'),
        help_text=_('All emails will be sent to this address as a Bcc copy'),
        validators=[multimail_validate],
        required=False,
        max_length=255,
    )
    mail_text_signature = I18nFormField(
        label=_('Signature'),
        required=False,
        widget=I18nTextarea,
        help_text=_('This will be attached to every email. Available placeholders: {event}'),
        validators=[PlaceholderValidator(['{event}'])],
        widget_kwargs={'attrs': {'rows': '4', 'placeholder': _('e.g. your contact details')}},
    )
    mail_html_renderer = forms.ChoiceField(label=_('HTML mail renderer'), required=True, choices=[])
    mail_text_order_placed = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_order_placed_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text=_(
            'If the order contains attendees with email addresses different from the person who orders the '
            'tickets, the following email will be sent out to the attendees.'
        ),
        required=False,
    )
    mail_text_order_placed_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_paid = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_order_paid_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text=_(
            'If the order contains attendees with email addresses different from the person who orders the '
            'tickets, the following email will be sent out to the attendees.'
        ),
        required=False,
    )
    mail_text_order_paid_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_free = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_order_free_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text=_(
            'If the order contains attendees with email addresses different from the person who orders the '
            'tickets, the following email will be sent out to the attendees.'
        ),
        required=False,
    )
    mail_text_order_free_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_meetup_registration = I18nFormField(
        label=_('Text sent to registration contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_meetup_registration_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text=_(
            'If the registration contains attendees with email addresses different from the person who '
            'registers, the following email will be sent out to the attendees.'
        ),
        required=False,
    )
    mail_text_meetup_registration_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )

    mail_text_order_changed = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_resend_link = I18nFormField(
        label=_('Text (sent by admin)'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_resend_all_links = I18nFormField(
        label=_('Text (requested by user)'),
        required=False,
        widget=I18nTextarea,
    )
    mail_days_order_expire_warning = forms.IntegerField(
        label=_('Number of days'),
        required=True,
        min_value=0,
        help_text=_(
            'This email will be sent out this many days before the order expires. If the '
            'value is 0, the mail will never be sent.'
        ),
    )
    mail_text_order_expire_warning = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_waiting_list = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_order_canceled = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_order_custom_mail = I18nFormField(
        label=_('Text'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_download_reminder = I18nFormField(
        label=_('Text sent to order contact address'),
        required=False,
        widget=I18nTextarea,
    )
    mail_send_download_reminder_attendee = forms.BooleanField(
        label=_('Send an email to attendees'),
        help_text=_(
            'If the order contains attendees with email addresses different from the person who orders the '
            'tickets, the following email will be sent out to the attendees.'
        ),
        required=False,
    )
    mail_text_download_reminder_attendee = I18nFormField(
        label=_('Text sent to attendees'),
        required=False,
        widget=I18nTextarea,
    )
    mail_days_download_reminder = forms.IntegerField(
        label=_('Number of days'),
        required=False,
        min_value=0,
        help_text=_(
            'This email will be sent out this many days before the order event starts. If the '
            'field is empty, the mail will never be sent.'
        ),
    )
    mail_text_order_placed_require_approval = I18nFormField(
        label=_('Received order'),
        required=False,
        widget=I18nTextarea,
    )
    mail_text_order_approved = I18nFormField(
        label=_('Approved order'),
        required=False,
        widget=I18nTextarea,
        help_text=_(
            'This will only be sent out for non-free orders. Free orders will receive the free order '
            'template from below instead.'
        ),
    )
    mail_text_order_approved_free = I18nFormField(
        label=_('Approved free order'),
        required=False,
        widget=I18nTextarea,
        help_text=_(
            'This will only be sent out for free orders. Non-free orders will receive the non-free order '
            'template from above instead.'
        ),
    )
    mail_text_order_denied = I18nFormField(
        label=_('Denied order'),
        required=False,
        widget=I18nTextarea,
    )
    base_context = {
        'mail_text_order_placed': ['event', 'order', 'payment'],
        'mail_text_order_placed_attendee': ['event', 'order', 'position'],
        'mail_text_order_placed_require_approval': ['event', 'order'],
        'mail_text_order_approved': ['event', 'order'],
        'mail_text_order_approved_free': ['event', 'order'],
        'mail_text_order_denied': ['event', 'order', 'comment'],
        'mail_text_order_paid': ['event', 'order', 'payment_info'],
        'mail_text_order_paid_attendee': ['event', 'order', 'position'],
        'mail_text_order_free': ['event', 'order'],
        'mail_text_order_free_attendee': ['event', 'order', 'position'],
        'mail_text_meetup_registration': ['event', 'order'],
        'mail_text_meetup_registration_attendee': ['event', 'order', 'position'],
        'mail_text_order_changed': ['event', 'order'],
        'mail_text_order_canceled': ['event', 'order'],
        'mail_text_order_expire_warning': ['event', 'order'],
        'mail_text_order_custom_mail': ['event', 'order'],
        'mail_text_download_reminder': ['event', 'order'],
        'mail_text_download_reminder_attendee': ['event', 'order', 'position'],
        'mail_text_resend_link': ['event', 'order'],
        'mail_text_waiting_list': ['event', 'waiting_list_entry'],
        'mail_text_resend_all_links': ['event', 'orders'],
    }

    def _set_field_placeholders(self, fn, base_parameters):
        phs = [f'{{{p}}}' for p in sorted(get_available_placeholders(self.event, base_parameters).keys())]
        ht = _('Available placeholders: {list}').format(list=', '.join(phs))
        if self.fields[fn].help_text:
            self.fields[fn].help_text += ' ' + str(ht)
        else:
            self.fields[fn].help_text = ht
        self.fields[fn].validators.append(PlaceholderValidator(phs))

    def __init__(self, *args, **kwargs):
        self.event = event = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        self.fields['mail_html_renderer'].choices = [
            (r.identifier, r.verbose_name) for r in event.get_html_mail_renderers().values()
        ]

        if not is_meetup_event(event):
            for field in ('mail_text_meetup_registration', 'mail_send_meetup_registration_attendee',
                          'mail_text_meetup_registration_attendee'):
                self.fields.pop(field, None)

        for k, v in self.base_context.items():
            if k in self.fields:
                self._set_field_placeholders(k, v)

        for k, v in list(self.fields.items()):
            if k.endswith('_attendee') and not event.settings.attendee_emails_asked:
                # If we don't ask for attendee emails, we can't send them anything and we don't need to clutter
                # the user interface with it
                del self.fields[k]



class TicketSettingsForm(SettingsForm):
    auto_fields = [
        'ticket_download',
        'ticket_download_date',
        'ticket_download_addons',
        'ticket_download_nonadm',
        'ticket_download_pending',
        'ticket_download_require_validated_email',
    ]
    ticket_secret_generator = forms.ChoiceField(
        label=_('Ticket code generator'),
        help_text=_('For advanced users, usually does not need to be changed.'),
        required=True,
        widget=forms.RadioSelect,
        choices=[],
    )


    def __init__(self, *args, **kwargs):
        event = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        self.fields['ticket_secret_generator'].choices = [
            (r.identifier, r.verbose_name) for r in event.ticket_secret_generators.values()
        ]

    def prepare_fields(self):
        # See clean()
        for k, v in self.fields.items():
            v._required = v.required
            v.required = False
            v.widget.is_required = False
            if isinstance(v, I18nFormField):
                v._required = v.one_required
                v.one_required = False
                v.widget.enabled_locales = self.locales

    def clean(self):
        # required=True files should only be required if the feature is enabled
        cleaned_data = super().clean()
        enabled = cleaned_data.get('ticket_download') is True
        if not enabled:
            return cleaned_data
        for k, v in self.fields.items():
            val = cleaned_data.get(k)
            if v._required and (val is None or val == ''):
                self.add_error(k, _('This field is required.'))
        return cleaned_data


class CommentForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        self.readonly = kwargs.pop('readonly', None)
        super().__init__(*args, **kwargs)
        if self.readonly:
            self.fields['comment'].widget.attrs['readonly'] = 'readonly'

    class Meta:
        model = Event
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'helper-width-100',
                }
            ),
        }


class CountriesAndEU(CachedCountries):
    override = {'ZZ': _('Any country'), 'EU': _('European Union')}
    first = ['ZZ', 'EU']
    cache_subkey = 'with_any_or_eu'


class TaxRuleLineForm(I18nForm):
    country = LazyTypedChoiceField(choices=CountriesAndEU(), required=False)
    address_type = forms.ChoiceField(
        choices=[
            ('', _('Any customer')),
            ('individual', _('Individual')),
            ('business', _('Business')),
            ('business_vat_id', _('Business with valid VAT ID')),
        ],
        required=False,
    )
    action = forms.ChoiceField(
        choices=[
            ('vat', _('Charge VAT')),
            ('reverse', _('Reverse charge')),
            ('no', _('No VAT')),
            ('block', _('Sale not allowed')),
        ],
    )
    rate = forms.DecimalField(
        label=_('Deviating tax rate'),
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=0,
        max_value=100,
    )
    invoice_text = I18nFormField(label=_('Text on invoice'), required=False, widget=I18nTextInput)


class I18nBaseFormSet(I18nFormSetMixin, forms.BaseFormSet):
    # compatibility shim for django-i18nfield library

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        if self.event:
            kwargs['locales'] = self.event.settings.get('locales')
        super().__init__(*args, **kwargs)


TaxRuleLineFormSet = formset_factory(TaxRuleLineForm, formset=I18nBaseFormSet, can_order=True, can_delete=True, extra=0)


class TaxRuleForm(I18nModelForm):
    class Meta:
        model = TaxRule
        fields = [
            'name',
            'rate',
            'price_includes_tax',
            'eu_reverse_charge',
            'home_country',
        ]


class WidgetCodeForm(forms.Form):
    subevent = forms.ModelChoiceField(
        label=pgettext_lazy('subevent', 'Date'),
        required=False,
        queryset=SubEvent.objects.none(),
    )
    language = forms.ChoiceField(label=_('Language'), required=True, choices=settings.LANGUAGES)
    voucher = forms.CharField(
        label=_('Pre-selected voucher'),
        required=False,
        help_text=_(
            'If set, the widget will show products as if this voucher has been entered and when a product is '
            'bought via the widget, this voucher will be used. This can for example be used to provide '
            'widgets that give discounts or unlock secret products.'
        ),
    )
    compatibility_mode = forms.BooleanField(
        label=_('Compatibility mode'),
        required=False,
        help_text=_(
            "Our regular widget doesn't work in all website builders. If you run into trouble, try using "
            'this compatibility mode.'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        super().__init__(*args, **kwargs)

        if self.event.has_subevents:
            self.fields['subevent'].queryset = self.event.subevents.all()
        else:
            del self.fields['subevent']

        self.fields['language'].choices = [(l, n) for l, n in settings.LANGUAGES if l in self.event.settings.locales]

    def clean_voucher(self):
        v = self.cleaned_data.get('voucher')
        if not v:
            return

        if not self.event.vouchers.filter(code=v).exists():
            raise ValidationError(_('The given voucher code does not exist.'))

        return v


class EventDeleteForm(forms.Form):
    error_messages = {
        'name_wrong': _('The event name you entered was not correct.'),
    }
    name = forms.CharField(
        max_length=255,
        label=_('Event name'),
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name != str(self.event.name):
            raise forms.ValidationError(
                self.error_messages['name_wrong'],
                code='name_wrong',
            )
        return name


class QuickSetupForm(I18nForm):
    currency = forms.ChoiceField(
        label=_('Event currency'),
        choices=Event.CURRENCY_CHOICES,
        required=True,
    )
    tax_name = I18nFormField(
        label=_('Tax name'),
        help_text=_('e.g. VAT'),
        required=False,
        widget=I18nTextInput,
    )
    tax_rate = forms.DecimalField(
        label=_('Tax rate (in %)'),
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        max_value=100,
    )
    tax_price_includes_tax = forms.BooleanField(
        label=_('The configured product prices include the tax amount'),
        required=False,
        initial=True,
    )
    show_quota_left = forms.BooleanField(
        label=_('Show number of tickets left'),
        help_text=_('Publicly show how many tickets of a certain type are still available.'),
        required=False,
    )
    waiting_list_enabled = forms.BooleanField(
        label=_('Waiting list'),
        help_text=_(
            'Once a ticket is sold out, people can add themselves to a waiting list. As soon as a ticket '
            'becomes available again, it will be reserved for the first person on the waiting list and this '
            'person will receive an email notification with a voucher that can be used to buy a ticket.'
        ),
        required=False,
    )
    ticket_download = forms.BooleanField(
        label=_('Ticket downloads'),
        help_text=_('Your customers will be able to download their tickets in PDF format.'),
        required=False,
    )
    attendee_names_required = forms.BooleanField(
        label=_('Require all attendees to fill in their names'),
        help_text=_(
            'By default, we will ask for names but not require them. You can turn this off completely in the settings.'
        ),
        required=False,
    )
    total_quota = forms.IntegerField(
        label=_('Total capacity'),
        min_value=0,
        widget=forms.NumberInput(attrs={'placeholder': '∞'}),
        required=False,
    )
    payment_stripe__enabled = forms.BooleanField(
        label=_('Payment via Stripe'),
        help_text=_(
            'Stripe is an online payments processor supporting credit cards and lots of other payment options. '
            'To accept payments via Stripe, you will need to set up an account with them, which takes less '
            'than five minutes using their simple interface.'
        ),
        required=False,
    )
    payment_paypal__enabled = forms.BooleanField(
        label=_('Payment via PayPal'),
        help_text=_(
            'PayPal is a widely used online payment service. To accept payments via PayPal, '
            'the platform must have PayPal configured in global settings.'
        ),
        required=False,
    )
    payment_banktransfer__enabled = forms.BooleanField(
        label=_('Payment by bank transfer'),
        help_text=_(
            'Your customers will be instructed to wire the money to your account. You can then import your '
            'bank statements to process the payments within eventyay, or mark them as paid manually.'
        ),
        required=False,
    )
    payment_manualpayment__enabled = forms.BooleanField(
        label=_('Manual payment'),
        help_text=_(
            'Your customers will be instructed to pay the money manually. You can then mark them as paid.'
        ),
        required=False,
    )
    require_registered_account_for_tickets = forms.BooleanField(
        label=REQUIRE_REGISTERED_ACCOUNT_LABEL,
        help_text=REQUIRE_REGISTERED_ACCOUNT_HELP_TEXT,
        required=False,
    )
    btf = BankTransfer.form_fields()
    payment_banktransfer_bank_details_type = btf['bank_details_type']
    payment_banktransfer_bank_details_sepa_name = btf['bank_details_sepa_name']
    payment_banktransfer_bank_details_sepa_iban = btf['bank_details_sepa_iban']
    payment_banktransfer_bank_details_sepa_bic = btf['bank_details_sepa_bic']
    payment_banktransfer_bank_details_sepa_bank = btf['bank_details_sepa_bank']
    payment_banktransfer_bank_details = btf['bank_details']

    def __init__(self, *args, **kwargs):
        from eventyay.base.plugins import get_all_plugins

        self.obj = kwargs.pop('event', None)
        self.locales = self.obj.settings.get('locales') if self.obj else kwargs.pop('locales', None)
        kwargs['locales'] = self.locales
        super().__init__(*args, **kwargs)
        
        plugins_available = {
            p.module for p in get_all_plugins(self.obj)
            if getattr(p, 'visible', True) and not p.name.startswith('.')
        }

        if 'eventyay.plugins.stripe' not in plugins_available:
            del self.fields['payment_stripe__enabled']
        if 'eventyay.plugins.paypal' not in plugins_available:
            del self.fields['payment_paypal__enabled']
            
        if 'eventyay.plugins.banktransfer' not in plugins_available:
            del self.fields['payment_banktransfer__enabled']
            del self.fields['payment_banktransfer_bank_details_type']
            del self.fields['payment_banktransfer_bank_details_sepa_name']
            del self.fields['payment_banktransfer_bank_details_sepa_iban']
            del self.fields['payment_banktransfer_bank_details_sepa_bic']
            del self.fields['payment_banktransfer_bank_details_sepa_bank']
            del self.fields['payment_banktransfer_bank_details']
        else:
            self.fields['payment_banktransfer_bank_details'].required = False
            
        if 'eventyay.plugins.manualpayment' not in plugins_available:
            del self.fields['payment_manualpayment__enabled']

        for f in self.fields.values():
            if 'data-required-if' in f.widget.attrs:
                del f.widget.attrs['data-required-if']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('payment_banktransfer__enabled'):
            provider = BankTransfer(self.obj)
            cleaned_data = provider.settings_form_clean(cleaned_data)
        
        tax_name = cleaned_data.get('tax_name')
        tax_rate = cleaned_data.get('tax_rate')
        if tax_name and tax_rate is None:
            self.add_error('tax_rate', _('Please enter a tax rate.'))
        elif tax_rate is not None and not tax_name:
            self.add_error('tax_name', _('Please enter a tax name.'))
            
        return cleaned_data


class QuickSetupProductForm(I18nForm):
    name = I18nFormField(
        max_length=200,  # Max length of Quota.name
        label=_('Product name'),
        widget=I18nTextInput,
    )
    default_price = forms.DecimalField(
        label=_('Price (optional)'),
        max_digits=13,
        decimal_places=2,
        required=False,
        localize=True,
        widget=forms.TextInput(attrs={'placeholder': _('Free')}),
    )
    quota = forms.IntegerField(
        label=_('Quantity available'),
        min_value=0,
        widget=forms.NumberInput(attrs={'placeholder': '∞'}),
        initial=100,
        required=False,
    )

    def clean_default_price(self):
        value = self.cleaned_data.get('default_price')
        if value is not None and value < 0:
            raise ValidationError(_('The price must not be negative.'))
        return value


class BaseQuickSetupProductFormSet(I18nFormSetMixin, forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.settings.get('locales')
        super().__init__(*args, **kwargs)


QuickSetupProductFormSet = formset_factory(
    QuickSetupProductForm,
    formset=BaseQuickSetupProductFormSet,
    can_order=False,
    can_delete=True,
    extra=0,
)


class ProductMetaPropertyForm(forms.ModelForm):
    class Meta:
        fields = ['name', 'default']
        widgets = {'default': forms.TextInput()}


class ConfirmTextForm(I18nForm):
    text = I18nFormField(
        widget=I18nTextarea,
        widget_kwargs={'attrs': {'rows': '2'}},
    )


class BaseConfirmTextFormSet(I18nFormSetMixin, forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.settings.get('locales')
        super().__init__(*args, **kwargs)


ConfirmTextFormset = formset_factory(
    ConfirmTextForm,
    formset=BaseConfirmTextFormSet,
    can_order=True,
    can_delete=True,
    extra=0,
)


class MeetupEventWizardBasicsForm(EventWizardBasicsForm):
    """Event basics for meetups: single-page quick-create form."""

    privacy_type = forms.ChoiceField(
        label=_('Visibility'),
        choices=PRIVACY_CHOICES,
        initial=PRIVACY_PUBLIC,
        widget=forms.Select(attrs={'class': 'form-control meetup-privacy-select'}),
        required=False,
    )
    location_type = forms.ChoiceField(
        label=_('Location'),
        choices=LOCATION_TYPE_CHOICES,
        initial=LOCATION_IN_PERSON,
        widget=forms.RadioSelect,
        required=False,
    )
    capacity_type = forms.ChoiceField(
        label=_('Capacity'),
        choices=CAPACITY_TYPE_CHOICES,
        initial=CAPACITY_UNLIMITED,
        widget=forms.RadioSelect,
        required=False,
    )
    registration_limit = forms.IntegerField(
        required=False,
        min_value=1,
        label=_('Registration limit'),
        help_text=_('Maximum number of attendees who can RSVP.'),
        widget=forms.NumberInput(attrs={'placeholder': _('e.g. 50')}),
    )
    registration_fee_type = forms.ChoiceField(
        label=_('Registration fee'),
        choices=REGISTRATION_FEE_CHOICES,
        initial=REGISTRATION_FEE_FREE,
        widget=forms.RadioSelect,
        required=False,
    )
    registration_fee = forms.DecimalField(
        required=False,
        min_value=Decimal('0.01'),
        decimal_places=2,
        max_digits=10,
        label=_('Registration fee amount'),
        help_text=_('Fee charged to attendees when registering for this meetup.'),
        widget=forms.NumberInput(attrs={'placeholder': _('e.g. 10.00'), 'step': '0.01', 'min': '0.01'}),
    )
    payment_stripe_publishable_key = forms.CharField(
        label=_('Publishable key'),
        required=False,
        help_text=_('Your Stripe publishable key (pk_live_... or pk_test_...).'),
        validators=(StripeKeyValidator(['pk_live_', 'pk_test_']),),
        widget=forms.TextInput(attrs={'placeholder': _('Publishable key')}),
    )
    payment_stripe_secret_key = forms.CharField(
        label=_('Secret key'),
        required=False,
        help_text=_('Your Stripe secret key (sk_live_..., sk_test_..., rk_live_..., or rk_test_...).'),
        validators=(StripeKeyValidator(['sk_live_', 'sk_test_', 'rk_live_', 'rk_test_']),),
        widget=forms.PasswordInput(render_value=True, attrs={'placeholder': _('Secret key'), 'autocomplete': 'new-password'}),
    )
    payment_stripe_merchant_country = forms.ChoiceField(
        label=_('Merchant country'),
        required=False,
        choices=[('', _('Select country'))] + list(countries),
        help_text=_('The country in which your Stripe-account is registered in. Usually, this is your country of residence.'),
    )
    frontpage_text = I18nFormField(
        widget=I18nTextarea,
        required=False,
        label=_('Event description'),
        help_text=_('Describe what this meetup is about, agenda, speakers, etc.'),
        widget_kwargs={'attrs': {'rows': '4', 'placeholder': _('Tell attendees about your meetup...')}},
    )
    logo_image = ExtFileField(
        label=_('Header image'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg', '.webp'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_('Upload a header image for your meetup banner and card. Recommended size: 1920 × 640 px.'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            build_video_form_fields(
                type_help_text=_('Optional: configure a live video stream for this meetup.')
            )
        )
        self.fields['slug'].required = False
        self.fields['location'].required = False
        currency_field = self.fields.get('currency')
        if currency_field is not None:
            currency_field.required = False
            if not self.initial.get('currency'):
                self.initial['currency'] = self._default_currency()

        event_currency = self.initial.get('currency') or (self.instance.currency if getattr(self, 'instance', None) and getattr(self.instance, 'currency', None) else self._default_currency())
        if 'registration_fee' in self.fields:
            self.fields['registration_fee'].help_text = _(
                'Fee charged to attendees when registering for this meetup (in {currency}).'
            ).format(currency=event_currency)
            self.fields['registration_fee'].widget.attrs['placeholder'] = _('e.g. 10.00 ({currency})').format(currency=event_currency)

        if self.initial.get('video_type') and self.initial.get('location'):
            self.initial['location_type'] = LOCATION_HYBRID
        elif self.initial.get('video_type') and not self.initial.get('location'):
            self.initial['location_type'] = LOCATION_VIRTUAL
        elif self.initial.get('location') and not self.initial.get('video_type'):
            self.initial['location_type'] = LOCATION_IN_PERSON
        else:
            self.initial['location_type'] = LOCATION_IN_PERSON

        if self.initial.get('registration_limit'):
            self.initial['capacity_type'] = CAPACITY_LIMITED
        else:
            self.initial['capacity_type'] = CAPACITY_UNLIMITED

        if self.initial.get('registration_fee') and Decimal(str(self.initial.get('registration_fee'))) > Decimal('0.00'):
            self.initial['registration_fee_type'] = REGISTRATION_FEE_PAID
        else:
            self.initial['registration_fee_type'] = REGISTRATION_FEE_FREE

        if 'registration_fee' in self.fields:
            self.fields['registration_fee']._required = True

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['data-eventyay-file-wrapper'] = 'disabled'
                field.widget.attrs['data-event-settings-image-tools'] = 'enabled'

    @staticmethod
    def _default_currency():
        return getattr(settings, 'DEFAULT_CURRENCY', 'USD')

    def clean_logo_image(self):
        img = self.cleaned_data.get('logo_image')
        if img and isinstance(img, UploadedFile):
            from PIL import Image, UnidentifiedImageError
            try:
                pil_image = Image.open(img)
                pil_image.verify()
                img.seek(0)
            except (UnidentifiedImageError, OSError, Exception):
                raise forms.ValidationError(
                    _('Upload a valid image. The file you uploaded was either not an image or a corrupted image.')
                )
        return img

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip()
        if not slug:
            charset = list('abcdefghjklmnpqrstuvwxyz3789')
            length = 6
            counter = 0
            while True:
                if length <= 10:
                    candidate = get_random_string(length=length, allowed_chars=charset)
                    length += 1
                else:
                    candidate = f'{get_random_string(length=4, allowed_chars=charset)}{counter}'
                    counter += 1
                if not self.organizer.events.filter(slug__iexact=candidate).exists():
                    slug = candidate
                    break
        elif Event.objects.filter(slug__iexact=slug, organizer=self.organizer).exists():
            raise forms.ValidationError(self.error_messages['duplicate_slug'], code='duplicate_slug')
        return slug.lower()

    def clean(self):
        cleaned_data = super().clean()
        loc_type = cleaned_data.get('location_type') or LOCATION_IN_PERSON

        if loc_type == LOCATION_VIRTUAL:
            cleaned_data.update({
                'location': '',
                'geo_lat': None,
                'geo_lon': None,
            })
        elif loc_type == LOCATION_IN_PERSON:
            cleaned_data['video_type'] = ''
            cleaned_data['video_url'] = ''

        if loc_type in (LOCATION_VIRTUAL, LOCATION_HYBRID):
            add_video_field_errors(self, cleaned_data.get('video_type'), cleaned_data.get('video_url'))

        cap_type = cleaned_data.get('capacity_type') or CAPACITY_UNLIMITED
        if cap_type == CAPACITY_UNLIMITED:
            cleaned_data['registration_limit'] = None
        elif cap_type == CAPACITY_LIMITED and not cleaned_data.get('registration_limit'):
            self.add_error('registration_limit', _('Please enter a capacity limit for limited registrations.'))

        fee_type = cleaned_data.get('registration_fee_type') or REGISTRATION_FEE_FREE
        if fee_type == REGISTRATION_FEE_FREE:
            cleaned_data['registration_fee'] = Decimal('0.00')
            cleaned_data['payment_stripe_publishable_key'] = ''
            cleaned_data['payment_stripe_secret_key'] = ''
            cleaned_data['payment_stripe_merchant_country'] = ''
            for f in ('registration_fee', 'payment_stripe_publishable_key', 'payment_stripe_secret_key', 'payment_stripe_merchant_country'):
                if f in self._errors:
                    del self._errors[f]
        elif fee_type == REGISTRATION_FEE_PAID:
            fee = cleaned_data.get('registration_fee')
            if not fee or fee <= Decimal('0.00'):
                self.add_error('registration_fee', _('Please enter a valid registration fee greater than 0.'))
            if not cleaned_data.get('payment_stripe_publishable_key'):
                self.add_error('payment_stripe_publishable_key', _('Please enter your Stripe publishable key.'))
            if not cleaned_data.get('payment_stripe_secret_key'):
                self.add_error('payment_stripe_secret_key', _('Please enter your Stripe secret key.'))
            if not cleaned_data.get('payment_stripe_merchant_country'):
                self.add_error('payment_stripe_merchant_country', _('Please select your Stripe merchant country.'))

        cleaned_data['privacy_type'] = cleaned_data.get('privacy_type') or PRIVACY_PUBLIC

        return cleaned_data
