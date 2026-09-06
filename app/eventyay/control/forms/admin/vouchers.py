from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled

from eventyay.base.forms import I18nModelForm
from eventyay.base.forms.widgets import SplitDateTimePickerWidget
from eventyay.base.models import Event, Organizer
from eventyay.base.models.vouchers import InvoiceVoucher, Voucher
from eventyay.control.forms import SplitDateTimeField


WAIVER_TYPE_CHOICES = [
    ('none', _('No effect')),
    ('percent_100', _('Waive all platform fees (100%)')),
    ('percent', _('Percentage platform fee discount')),
    ('subtract', _('Fixed platform fee credit')),
]

SCOPE_TYPE_CHOICES = [
    ('specific_events', _('Specific events')),
    ('all_by_organisers', _('All events by selected organisers')),
    ('both', _('Both selected events and selected organisers')),
    ('platform_wide', _('Platform-wide (all events and organisers)')),
]


class InvoiceVoucherForm(I18nModelForm):
    waiver_type = forms.ChoiceField(
        choices=WAIVER_TYPE_CHOICES,
        label=_('Waiver type'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    scope_type = forms.ChoiceField(
        choices=SCOPE_TYPE_CHOICES,
        label=_('Apply voucher to'),
        required=False,
        widget=forms.RadioSelect,
    )

    event_effect = forms.ModelMultipleChoiceField(
        queryset=Event.objects.none(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2-multi',
            'data-placeholder': _('Search and select events...'),
            'multiple': 'multiple',
        }),
        required=False,
        label=_('Events'),
        help_text=_('The voucher will be valid for the selected events.'),
    )
    organizer_effect = forms.ModelMultipleChoiceField(
        queryset=Organizer.objects.none(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2-multi',
            'data-placeholder': _('Search and select organisers...'),
            'multiple': 'multiple',
        }),
        required=False,
        label=_('Organisers'),
        help_text=_('The voucher will be valid for all events under the selected organisers.'),
    )

    class Meta:
        model = InvoiceVoucher
        localized_fields = '__all__'
        fields = [
            'code',
            'status',
            'valid_until',
            'comment',
            'price_mode',
            'value',
            'max_usages',
            'budget',
            'allow_partial_usage',
            'event_effect',
            'organizer_effect',
        ]
        field_classes = {
            'valid_until': SplitDateTimeField,
        }
        widgets = {
            'valid_until': SplitDateTimePickerWidget(),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Use letters and numbers. Code must be unique.'),
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Optional note for internal reference'),
            }),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_usages': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'code': _('Voucher code'),
            'status': _('Status'),
            'valid_until': _('Valid until'),
            'comment': _('Internal note'),
            'price_mode': _('Waiver type'),
            'value': _('Fee waiver value'),
            'max_usages': _('Maximum redemptions'),
            'budget': _('Maximum fee waiver budget'),
            'allow_partial_usage': _('Allow partial usage'),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if instance:
            self.fields['event_effect'].initial = instance.limit_events.all()
            self.fields['organizer_effect'].initial = instance.limit_organizer.all()
            # Derive waiver_type from price_mode + value
            if instance.price_mode == 'percent' and instance.value == 100:
                self.fields['waiver_type'].initial = 'percent_100'
            elif instance.price_mode == 'percent':
                self.fields['waiver_type'].initial = 'percent'
            elif instance.price_mode == 'subtract':
                self.fields['waiver_type'].initial = 'subtract'
            else:
                self.fields['waiver_type'].initial = 'none'
            # Derive scope_type
            has_events = instance.limit_events.exists()
            has_orgs = instance.limit_organizer.exists()
            if has_events and has_orgs:
                self.fields['scope_type'].initial = 'both'
            elif has_orgs:
                self.fields['scope_type'].initial = 'all_by_organisers'
            elif has_events:
                self.fields['scope_type'].initial = 'specific_events'
            else:
                self.fields['scope_type'].initial = 'platform_wide'
        else:
            self.fields['waiver_type'].initial = 'none'
            self.fields['scope_type'].initial = 'specific_events'

        with scopes_disabled():
            self.fields['event_effect'].queryset = Event.objects.all()
            self.fields['organizer_effect'].queryset = Organizer.objects.all()

        # Hide the raw price_mode field — we use waiver_type instead
        self.fields['price_mode'].widget = forms.HiddenInput()
        self.fields['price_mode'].required = False

    def clean(self):
        data = super().clean()

        # Map waiver_type back to price_mode + value
        waiver_type = data.get('waiver_type', 'none')
        if waiver_type == 'percent_100':
            data['price_mode'] = 'percent'
            data['value'] = Decimal('100.00')
        elif waiver_type == 'percent':
            data['price_mode'] = 'percent'
            if not data.get('value'):
                self.add_error('value', _('Please enter a percentage value.'))
            elif data['value'] < 0 or data['value'] > 100:
                self.add_error('value', _('Percentage values must be between 0 and 100.'))
        elif waiver_type == 'subtract':
            data['price_mode'] = 'subtract'
            if not data.get('value'):
                self.add_error('value', _('Please enter a fee credit amount.'))
        else:
            data['price_mode'] = 'none'
            data['value'] = None

        scope_type = data.get('scope_type')
        if scope_type == 'platform_wide':
            data['event_effect'] = []
            data['organizer_effect'] = []
        elif scope_type == 'specific_events':
            data['organizer_effect'] = []
        elif scope_type == 'all_by_organisers':
            data['event_effect'] = []

        # Validate scope for active vouchers
        status = data.get('status', InvoiceVoucher.STATUS_ACTIVE)
        if status == InvoiceVoucher.STATUS_ACTIVE:
            if not data.get('code'):
                self.add_error('code', _('Voucher code is required for active vouchers.'))
            if not data.get('valid_until'):
                self.add_error('valid_until', _('Valid until is required for active vouchers.'))
            if waiver_type == 'none':
                self.add_error('waiver_type', _('Please select a waiver type for active vouchers.'))
            if scope_type != 'platform_wide' and not data.get('event_effect') and not data.get('organizer_effect'):
                self.add_error(
                    'event_effect',
                    _('Select at least one event or organiser, or explicitly choose platform-wide scope.'),
                )

        Voucher.clean_value_and_budget(data)

        return data

    def _post_clean(self):
        super()._post_clean()
        for field, error_list in list(self._errors.items()):
            seen = set()
            unique_errors = []
            for err in error_list:
                msg = str(err)
                if msg not in seen:
                    seen.add(msg)
                    unique_errors.append(err)
            self._errors[field] = self.error_class(unique_errors, renderer=self.renderer)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Apply the mapped price_mode from clean()
        instance.price_mode = self.cleaned_data.get('price_mode', 'none')
        if self.cleaned_data.get('value') is not None:
            instance.value = self.cleaned_data['value']

        if commit:
            instance.save()
            instance.limit_events.set(self.cleaned_data.get('event_effect', []))
            instance.limit_organizer.set(self.cleaned_data.get('organizer_effect', []))
            self.save_m2m()
        else:
            # When commit=False, the caller is responsible for saving the instance and M2M fields
            def save_m2m():
                super(InvoiceVoucherForm, self).save_m2m()
                instance.limit_events.set(self.cleaned_data.get('event_effect', []))
                instance.limit_organizer.set(self.cleaned_data.get('organizer_effect', []))
            self.save_m2m = save_m2m

        return instance


class VoucherFilterForm(forms.Form):
    """Filter form for the Platform Fee Vouchers overview page."""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search voucher code, event, organiser...'),
        }),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('All statuses')),
            ('active', _('Active')),
            ('disabled', _('Disabled')),
            ('expired', _('Expired')),
            ('used_up', _('Used up')),
            ('draft', _('Draft')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Status'),
    )
    scope = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('All scopes')),
            ('events', _('Specific events')),
            ('organisers', _('By organisers')),
            ('platform_wide', _('Platform-wide')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Scope'),
    )
    effect = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('All effects')),
            ('percent', _('Percentage discount')),
            ('subtract', _('Fixed credit')),
            ('set', _('Set price')),
            ('none', _('No effect')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Effect'),
    )
    valid_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': _('Select date range'),
        }),
        label=_('Valid until'),
    )

    @property
    def filtered(self) -> bool:
        if not hasattr(self, 'cleaned_data'):
            return False
        return any(self.cleaned_data.get(f) for f in self.fields)
