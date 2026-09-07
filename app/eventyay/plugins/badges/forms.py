import json

from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Product, Voucher
from eventyay.plugins.badges.models import BadgeLayout, BadgeProduct, BadgeVoucher
from eventyay.plugins.badges.utils import (
    DEFAULT_BADGE_ENABLED_PLACEHOLDERS,
    format_badge_option_labels,
    get_badge_customizable_fields,
    get_categorized_badge_placeholders,
    get_event_allowed_badge_placeholders,
)


def _sync_badge_assignments(model, layout, related_name, selected):
    selected_ids = set(selected.values_list('pk', flat=True))
    model.objects.filter(layout=layout).exclude(**{f'{related_name}_id__in': selected_ids}).delete()
    for item in selected:
        model.objects.update_or_create(**{related_name: item}, defaults={'layout': layout})


class BadgeLayoutForm(forms.ModelForm):
    class Meta:
        model = BadgeLayout
        fields = ('name',)


class BadgeLayoutSettingsForm(forms.Form):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        required=False,
        label=_('Products assigned to this layout'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
    )
    vouchers = forms.ModelMultipleChoiceField(
        queryset=Voucher.objects.none(),
        required=False,
        label=_('Vouchers assigned to this layout'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
    )
    allow_customization = forms.BooleanField(
        required=False,
        label=_('Allow badge customization'),
    )
    allow_badge_editing = forms.BooleanField(
        required=False,
        label=_('Allow badge editing'),
        help_text=_(
            'When enabled, check-in staff can edit badge text for the selected fields before printing an updated badge.'
        ),
    )
    ask_user_fields = forms.MultipleChoiceField(
        required=False,
        label=_('Badge fields'),
        widget=forms.CheckboxSelectMultiple,
    )
    required_badge_fields = forms.MultipleChoiceField(
        required=False,
        label=_('Required badge fields'),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        self.layout = kwargs.pop('layout')
        super().__init__(*args, **kwargs)

        self.fields['products'].queryset = self.event.products.order_by('category__position', 'position')
        self.fields['products'].initial = list(self.layout.product_assignments.values_list('product_id', flat=True))
        self.fields['vouchers'].queryset = self.event.vouchers.order_by('code')
        self.fields['vouchers'].initial = list(self.layout.voucher_assignments.values_list('voucher_id', flat=True))
        if self.layout.default:
            self.fields['products'].help_text = _(
                'Products not explicitly assigned to another layout will also use the default layout.'
            )
            self.fields['vouchers'].help_text = _(
                'Vouchers not explicitly assigned to another layout will fall back to the product or default layout.'
            )

        self.customizable_fields = get_badge_customizable_fields(self.event, self.layout)
        choices = [(field['key'], field['label']) for field in self.customizable_fields]
        valid_keys = {choice[0] for choice in choices}
        initial_keys = [key for key in self.layout.ask_user_fields_data if key in valid_keys]

        self.fields['allow_customization'].initial = self.layout.allow_customization
        self.fields['allow_badge_editing'].initial = self.layout.allow_badge_editing
        self.fields['ask_user_fields'].choices = choices
        self.fields['ask_user_fields'].initial = initial_keys
        self.fields['required_badge_fields'].choices = choices
        self.fields['required_badge_fields'].initial = [
            key for key in self.layout.required_badge_fields_data if key in valid_keys
        ]

        if not choices:
            self.fields['allow_customization'].disabled = True
            self.fields['allow_badge_editing'].disabled = True
            self.fields['allow_customization'].help_text = _(
                'This layout does not currently contain any dynamic text fields that can be customized.'
            )

    def clean(self):
        cleaned_data = super().clean()
        if not self.customizable_fields:
            cleaned_data['allow_customization'] = False
            cleaned_data['allow_badge_editing'] = False
            cleaned_data['ask_user_fields'] = []
            cleaned_data['required_badge_fields'] = []
            return cleaned_data

        if not cleaned_data.get('allow_customization'):
            cleaned_data['ask_user_fields'] = []
            cleaned_data['required_badge_fields'] = []
            cleaned_data['allow_badge_editing'] = False

        # Ensure required fields are also in ask_user_fields
        required_fields = set(cleaned_data.get('required_badge_fields', []))
        ask_user = set(cleaned_data.get('ask_user_fields', []))
        if required_fields - ask_user:
            cleaned_data['ask_user_fields'] = list(ask_user | required_fields)

        return cleaned_data

    @transaction.atomic
    def save(self):
        _sync_badge_assignments(BadgeProduct, self.layout, 'product', self.cleaned_data['products'])
        _sync_badge_assignments(BadgeVoucher, self.layout, 'voucher', self.cleaned_data['vouchers'])

        self.layout.allow_customization = self.cleaned_data['allow_customization']
        self.layout.allow_badge_editing = self.cleaned_data['allow_badge_editing']
        self.layout.ask_user_fields_data = self.cleaned_data['ask_user_fields']
        self.layout.required_badge_fields_data = self.cleaned_data['required_badge_fields']
        self.layout.save(
            update_fields=['allow_customization', 'allow_badge_editing', 'ask_user_fields', 'required_badge_fields']
        )
        return self.layout


class BadgeOptionsWidget(forms.CheckboxSelectMultiple):
    def __init__(self, *args, required_keys=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.required_keys = set(required_keys)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if str(value) in self.required_keys:
            option['attrs']['disabled'] = True
            option['attrs']['checked'] = True
        return option


class BadgeOptionsField(forms.MultipleChoiceField):
    widget = BadgeOptionsWidget
    badge_option = True

    def __init__(self, *args, hidden_initial=None, required_keys=(), **kwargs):
        kwargs['widget'] = self.widget(required_keys=required_keys)
        super().__init__(*args, required=False, **kwargs)
        self._choice_order = [str(value) for value, _label in self.choices]
        self.initial = self.get_meta_initial(hidden_initial)
        self.required_keys = set(required_keys)

    def get_meta_initial(self, hidden_values):
        if isinstance(hidden_values, str):
            hidden_values = [hidden_values]
        hidden_values = {str(value) for value in (hidden_values or [])}
        return [value for value in self._choice_order if value not in hidden_values]

    def get_display_value(self, hidden_values):
        visible_values = set(self.get_meta_initial(hidden_values))
        visible_labels = [label for value, label in self.choices if str(value) in visible_values]
        return format_badge_option_labels(visible_labels)

    def clean(self, value):
        value = value or []
        if isinstance(value, (list, tuple)):
            value = list(set(value) | self.required_keys)

        selected_values = set(super().clean(value))
        return [choice for choice in self._choice_order if choice not in selected_values]


class MultiplePlaceholdersWidget(forms.CheckboxSelectMultiple):
    template_name = 'pretixplugins/badges/placeholder_grid_select.html'
    option_template_name = 'pretixplugins/badges/placeholder_grid_option.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sample_map = {}
        self.categories = []

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['default_placeholders'] = DEFAULT_BADGE_ENABLED_PLACEHOLDERS
        ctx['categories'] = self.categories
        ctx['sample_map'] = self.sample_map
        return ctx

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opt = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        opt['sample'] = self.sample_map.get(str(value), '')
        opt['is_default'] = str(value) in DEFAULT_BADGE_ENABLED_PLACEHOLDERS
        return opt


class BadgeSettingsForm(forms.Form):
    allowed_placeholders = forms.MultipleChoiceField(
        required=False,
        label=_('Allowed badge placeholders'),
        widget=MultiplePlaceholdersWidget,
        help_text=_(
            'Select which placeholders are available for badge designs in this event. '
            'Unchecked placeholders will be hidden from the badge editor.'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        super().__init__(*args, **kwargs)

        categories = get_categorized_badge_placeholders(self.event)
        grouped_choices = []
        sample_map = {}
        for cat in categories:
            cat_choices = []
            for item in cat['items']:
                cat_choices.append((item['key'], item['label']))
                sample_map[item['key']] = item['sample']
            grouped_choices.append((cat['label'], cat_choices))

        self.fields['allowed_placeholders'].choices = grouped_choices
        self.fields['allowed_placeholders'].widget.sample_map = sample_map
        self.fields['allowed_placeholders'].widget.categories = categories
        self.fields['allowed_placeholders'].initial = get_event_allowed_badge_placeholders(self.event)

    def save(self):
        allowed = list(self.cleaned_data.get('allowed_placeholders') or [])
        self.event.settings.badge_allowed_placeholders = json.dumps(allowed)
        return allowed


EventBadgeSettingsForm = BadgeSettingsForm
