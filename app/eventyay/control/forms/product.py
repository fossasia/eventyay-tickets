from decimal import Decimal
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.forms.formsets import DELETION_FIELD_NAME
from django.urls import reverse
from django.utils.translation import (
    gettext as __,
)
from django.utils.translation import (
    gettext_lazy as _,
)
from django.utils.translation import (
    pgettext_lazy,
)
from django_scopes.forms import (
    SafeModelChoiceField,
    SafeModelMultipleChoiceField,
)
from i18nfield.forms import I18nFormField, I18nTextarea

from eventyay.base.channels import get_all_sales_channels
from eventyay.base.forms import I18nFormSet, I18nModelForm
from eventyay.base.forms.widgets import DatePickerWidget
from eventyay.base.models import (
    Product,
    ProductCategory,
    ProductVariation,
    Question,
    QuestionOption,
    Quota,
)
from eventyay.base.models.product import ProductAddOn, ProductBundle, ProductMetaValue
from eventyay.base.signals import product_copy_data
from eventyay.control.forms import SplitDateTimeField, SplitDateTimePickerWidget
from eventyay.control.forms.widgets import Select2
from eventyay.helpers.models import modelcopy
from eventyay.helpers.money import change_decimal_field


class CategoryForm(I18nModelForm):
    class Meta:
        model = ProductCategory
        localized_fields = '__all__'
        fields = ['name', 'internal_name', 'description', 'is_addon']


class QuestionForm(I18nModelForm):
    question = I18nFormField(label=_('Question'), widget_kwargs={'attrs': {'rows': 2}}, widget=I18nTextarea)

    def removeDesOption(self):
        choices = list(self.fields['type'].choices)
        for value in choices:
            if value[0] == Question.TYPE_DESCRIPTION:
                choices.remove(value)
                break
        self.fields['type'].choices = choices

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.removeDesOption()
        self.fields['products'].queryset = self.instance.event.products.all()
        self.fields['products'].required = True
        self.fields['dependency_question'].queryset = self.instance.event.questions.filter(
            type__in=(
                Question.TYPE_BOOLEAN,
                Question.TYPE_CHOICE,
                Question.TYPE_CHOICE_MULTIPLE,
            ),
            ask_during_checkin=False,
        )
        if self.instance.pk:
            self.fields['dependency_question'].queryset = self.fields['dependency_question'].queryset.exclude(
                pk=self.instance.pk
            )
        self.fields['identifier'].required = False
        self.fields['dependency_values'].required = False
        self.fields['help_text'].widget.attrs['rows'] = 3

    def clean_dependency_values(self):
        val = self.data.getlist('dependency_values')
        return val

    def clean_dependency_question(self):
        dep = val = self.cleaned_data.get('dependency_question')
        if dep:
            if dep.ask_during_checkin:
                raise ValidationError(_('Question cannot depend on a question asked during check-in.'))

            seen_ids = {self.instance.pk} if self.instance else set()
            while dep:
                if dep.pk in seen_ids:
                    raise ValidationError(_('Circular dependency between questions detected.'))
                seen_ids.add(dep.pk)
                dep = dep.dependency_question
        return val

    def clean_ask_during_checkin(self):
        val = self.cleaned_data.get('ask_during_checkin')

        if val and self.cleaned_data.get('type') in Question.ASK_DURING_CHECKIN_UNSUPPORTED:
            raise ValidationError(_('This type of question cannot be asked during check-in.'))

        return val

    def clean(self):
        d = super().clean()
        if d.get('dependency_question') and not d.get('dependency_values'):
            raise ValidationError({'dependency_values': [_('This field is required')]})
        if d.get('dependency_question') and d.get('ask_during_checkin'):
            raise ValidationError(_('Dependencies between questions are not supported during check-in.'))
        return d

    class Meta:
        model = Question
        localized_fields = '__all__'
        fields = [
            'question',
            'help_text',
            'description',
            'type',
            'required',
            'ask_during_checkin',
            'hidden',
            'identifier',
            'products',
            'dependency_question',
            'dependency_values',
            'print_on_invoice',
            'valid_number_min',
            'valid_number_max',
            'valid_datetime_min',
            'valid_datetime_max',
            'valid_date_min',
            'valid_date_max',
        ]
        widgets = {
            'valid_datetime_min': SplitDateTimePickerWidget(),
            'valid_datetime_max': SplitDateTimePickerWidget(),
            'valid_date_min': DatePickerWidget(),
            'valid_date_max': DatePickerWidget(),
            'products': forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
            'dependency_values': forms.SelectMultiple,
        }
        field_classes = {
            'valid_datetime_min': SplitDateTimeField,
            'valid_datetime_max': SplitDateTimeField,
            'products': SafeModelMultipleChoiceField,
            'dependency_question': SafeModelChoiceField,
        }


class DescriptionForm(QuestionForm):
    question = I18nFormField(
        label=_('Description Title'),
        widget_kwargs={'attrs': {'rows': 2}},
        widget=I18nTextarea,
    )
    description = I18nFormField(
        label=_('Description'),
        widget_kwargs={'attrs': {'rows': 3}},
        widget=I18nTextarea,
        initial='hahaha',
    )

    def removeDesOption(self):
        # just override parent 's function
        pass

    def __init__(self, *args, **kwargs):
        kwargs['initial'] = {
            'type': 'DES',
        }
        super().__init__(*args, **kwargs)


class QuestionOptionForm(I18nModelForm):
    class Meta:
        model = QuestionOption
        localized_fields = '__all__'
        fields = [
            'answer',
        ]


class QuotaForm(I18nModelForm):
    def __init__(self, **kwargs):
        self.instance = kwargs.get('instance', None)
        self.event = kwargs.get('event')
        products = kwargs.pop('products', None) or self.event.products.prefetch_related('variations')
        self.original_instance = modelcopy(self.instance) if self.instance else None
        initial = kwargs.get('initial', {})
        if self.instance and self.instance.pk and 'productvars' not in initial:
            initial['productvars'] = [str(i.pk) for i in self.instance.products.all()] + [
                '{}-{}'.format(v.product_id, v.pk) for v in self.instance.variations.all()
            ]
        kwargs['initial'] = initial
        super().__init__(**kwargs)

        choices = []
        for product in products:
            if len(product.variations.all()) > 0:
                for v in product.variations.all():
                    choices.append(('{}-{}'.format(product.pk, v.pk), '{} – {}'.format(product, v.value)))
            else:
                choices.append(('{}'.format(product.pk), str(product)))

        self.fields['productvars'] = forms.MultipleChoiceField(
            label=_('Products'),
            required=False,
            choices=choices,
            widget=forms.CheckboxSelectMultiple,
        )

        if self.event.has_subevents:
            self.fields['subevent'].queryset = self.event.subevents.all()
            self.fields['subevent'].widget = Select2(
                attrs={
                    'data-model-select2': 'event',
                    'data-select2-url': reverse(
                        'control:event.subevents.select2',
                        kwargs={
                            'event': self.event.slug,
                            'organizer': self.event.organizer.slug,
                        },
                    ),
                    'data-placeholder': pgettext_lazy('subevent', 'Date'),
                }
            )
            self.fields['subevent'].widget.choices = self.fields['subevent'].choices
            self.fields['subevent'].required = True
        else:
            del self.fields['subevent']

    class Meta:
        model = Quota
        localized_fields = '__all__'
        fields = [
            'name',
            'size',
            'subevent',
            'close_when_sold_out',
            'release_after_exit',
        ]
        field_classes = {
            'subevent': SafeModelChoiceField,
        }

    def save(self, *args, **kwargs):
        creating = not self.instance.pk
        inst = super().save(*args, **kwargs)

        selected_products = set(
            list(self.event.products.filter(id__in=[i.split('-')[0] for i in self.cleaned_data['productvars']]))
        )
        selected_variations = list(
            ProductVariation.objects.filter(
                product__event=self.event,
                id__in=[i.split('-')[1] for i in self.cleaned_data['productvars'] if '-' in i],
            )
        )

        current_products = [] if creating else self.instance.products.all()
        current_variations = [] if creating else self.instance.variations.all()

        self.instance.products.remove(*[i for i in current_products if i not in selected_products])
        self.instance.products.add(*[i for i in selected_products if i not in current_products])
        self.instance.variations.remove(*[i for i in current_variations if i not in selected_variations])
        self.instance.variations.add(*[i for i in selected_variations if i not in current_variations])
        return inst


class ProductCreateForm(I18nModelForm):
    NONE = 'none'
    EXISTING = 'existing'
    NEW = 'new'
    has_variations = forms.BooleanField(
        label=_('The product should exist in multiple variations'),
        help_text=_(
            'Select this option e.g. for t-shirts that come in multiple sizes. '
            'You can select the variations in the next step.'
        ),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs['event']
        self.user = kwargs.pop('user')
        kwargs.setdefault('initial', {})
        kwargs['initial'].setdefault('admission', True)
        super().__init__(*args, **kwargs)

        self.fields['category'].queryset = self.instance.event.categories.all()
        self.fields['category'].widget = Select2(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.products.categories.select2',
                    kwargs={
                        'event': self.instance.event.slug,
                        'organizer': self.instance.event.organizer.slug,
                    },
                ),
                'data-placeholder': _('No category'),
            }
        )
        self.fields['category'].widget.choices = self.fields['category'].choices

        self.fields['tax_rule'].queryset = self.instance.event.tax_rules.all()
        change_decimal_field(self.fields['default_price'], self.instance.event.currency)
        self.fields['tax_rule'].empty_label = _('No taxation')
        self.fields['copy_from'] = forms.ModelChoiceField(
            label=_('Copy product information'),
            queryset=self.event.products.all(),
            widget=forms.Select,
            empty_label=_('Do not copy'),
            required=False,
        )
        if self.event.tax_rules.exists():
            self.fields['tax_rule'].required = True

        if not self.event.has_subevents:
            choices = [
                (self.NONE, _('Do not add to a quota now')),
                (self.EXISTING, _('Add product to an existing quota')),
                (self.NEW, _('Create a new quota for this product')),
            ]
            if not self.event.quotas.exists():
                choices.remove(choices[1])

            self.fields['quota_option'] = forms.ChoiceField(
                label=_('Quota options'),
                widget=forms.RadioSelect,
                choices=choices,
                initial=self.NONE,
                required=False,
            )

            self.fields['quota_add_existing'] = forms.ModelChoiceField(
                label=_('Add to existing quota'),
                widget=forms.Select(),
                queryset=self.instance.event.quotas.all(),
                required=False,
            )

            self.fields['quota_add_new_name'] = forms.CharField(
                label=_('Name'),
                max_length=200,
                widget=forms.TextInput(attrs={'placeholder': _('New quota name')}),
                required=False,
            )

            self.fields['quota_add_new_size'] = forms.IntegerField(
                min_value=0,
                label=_('Size'),
                widget=forms.TextInput(attrs={'placeholder': _('Number of tickets')}),
                help_text=_('Leave empty for an unlimited number of tickets.'),
                required=False,
            )

    def save(self, *args, **kwargs):
        if self.cleaned_data.get('copy_from'):
            fields = (
                'description',
                'active',
                'available_from',
                'available_until',
                'require_voucher',
                'hide_without_voucher',
                'allow_cancel',
                'min_per_order',
                'max_per_order',
                'generate_tickets',
                'checkin_attention',
                'free_price',
                'original_price',
                'sales_channels',
                'issue_giftcard',
                'require_approval',
                'allow_waitinglist',
                'show_quota_left',
                'hidden_if_available',
                'require_bundling',
                'checkin_attention',
            )
            for f in fields:
                setattr(self.instance, f, getattr(self.cleaned_data['copy_from'], f))
        else:
            # Add to all sales channels by default
            self.instance.sales_channels = list(get_all_sales_channels().keys())

        self.instance.position = (self.event.products.aggregate(p=Max('position'))['p'] or 0) + 1
        instance = super().save(*args, **kwargs)

        if not self.event.has_subevents and not self.cleaned_data.get('has_variations'):
            if (
                self.cleaned_data.get('quota_option') == self.EXISTING
                and self.cleaned_data.get('quota_add_existing') is not None
            ):
                quota = self.cleaned_data.get('quota_add_existing')
                quota.products.add(self.instance)
                quota.log_action(
                    'pretix.event.quota.changed',
                    user=self.user,
                    data={'product_added': self.instance.pk},
                )
            elif self.cleaned_data.get('quota_option') == self.NEW:
                quota_name = self.cleaned_data.get('quota_add_new_name')
                quota_size = self.cleaned_data.get('quota_add_new_size')

                quota = Quota.objects.create(event=self.event, name=quota_name, size=quota_size)
                quota.products.add(self.instance)
                quota.log_action(
                    'pretix.event.quota.added',
                    user=self.user,
                    data={
                        'name': quota_name,
                        'size': quota_size,
                        'products': [self.instance.pk],
                    },
                )

        if self.cleaned_data.get('has_variations'):
            if self.cleaned_data.get('copy_from') and self.cleaned_data.get('copy_from').has_variations:
                for variation in self.cleaned_data['copy_from'].variations.all():
                    ProductVariation.objects.create(
                        product=instance,
                        value=variation.value,
                        active=variation.active,
                        position=variation.position,
                        default_price=variation.default_price,
                        description=variation.description,
                        original_price=variation.original_price,
                    )
            else:
                ProductVariation.objects.create(product=instance, value=__('Standard'))

        if self.cleaned_data.get('copy_from'):
            for question in self.cleaned_data['copy_from'].questions.all():
                question.products.add(instance)
            for a in self.cleaned_data['copy_from'].addons.all():
                instance.addons.create(
                    addon_category=a.addon_category,
                    min_count=a.min_count,
                    max_count=a.max_count,
                    price_included=a.price_included,
                    position=a.position,
                )
            for b in self.cleaned_data['copy_from'].bundles.all():
                instance.bundles.create(
                    bundled_product=b.bundled_product,
                    bundled_variation=b.bundled_variation,
                    count=b.count,
                    designated_price=b.designated_price,
                )

            product_copy_data.send(
                sender=self.event,
                source=self.cleaned_data['copy_from'],
                target=instance,
            )

        return instance

    def clean(self):
        cleaned_data = super().clean()

        if not self.event.has_subevents:
            if cleaned_data.get('quota_option') == self.NEW:
                if not self.cleaned_data.get('quota_add_new_name'):
                    raise forms.ValidationError({'quota_add_new_name': [_('Quota name is required.')]})
            elif cleaned_data.get('quota_option') == self.EXISTING:
                if not self.cleaned_data.get('quota_add_existing'):
                    raise forms.ValidationError({'quota_add_existing': [_('Please select a quota.')]})

        return cleaned_data

    class Meta:
        model = Product
        localized_fields = '__all__'
        fields = [
            'name',
            'internal_name',
            'category',
            'admission',
            'default_price',
            'tax_rule',
        ]


class ShowQuotaNullBooleanSelect(forms.NullBooleanSelect):
    def __init__(self, attrs=None):
        choices = (
            ('unknown', _('(Event default)')),
            ('true', _('Yes')),
            ('false', _('No')),
        )
        super(forms.NullBooleanSelect, self).__init__(attrs, choices)


class TicketNullBooleanSelect(forms.NullBooleanSelect):
    def __init__(self, attrs=None):
        choices = (
            ('unknown', _('Choose automatically depending on event settings')),
            ('true', _('Yes, if ticket generation is enabled in general')),
            ('false', _('Never')),
        )
        super(forms.NullBooleanSelect, self).__init__(attrs, choices)


class ProductUpdateForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tax_rule'].queryset = self.instance.event.tax_rules.all()
        self.fields['description'].widget.attrs['placeholder'] = _(
            'e.g. This reduced price is available for full-time students, jobless and people '
            'over 65. This ticket includes access to all parts of the event, except the VIP '
            'area.'
        )
        if self.event.tax_rules.exists():
            self.fields['tax_rule'].required = True
        self.fields['description'].widget.attrs['rows'] = '4'
        self.fields['sales_channels'] = forms.MultipleChoiceField(
            label=_('Sales channels'),
            required=False,
            choices=((c.identifier, c.verbose_name) for c in get_all_sales_channels().values()),
            widget=forms.CheckboxSelectMultiple,
        )
        change_decimal_field(self.fields['default_price'], self.event.currency)
        self.fields['hidden_if_available'].queryset = self.event.quotas.all()
        self.fields['hidden_if_available'].widget = Select2(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.products.quotas.select2',
                    kwargs={
                        'event': self.event.slug,
                        'organizer': self.event.organizer.slug,
                    },
                ),
                'data-placeholder': _('Shown independently of other products'),
            }
        )
        self.fields['hidden_if_available'].widget.choices = self.fields['hidden_if_available'].choices
        self.fields['hidden_if_available'].required = False

        self.fields['category'].queryset = self.instance.event.categories.all()
        self.fields['category'].widget = Select2(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.products.categories.select2',
                    kwargs={
                        'event': self.instance.event.slug,
                        'organizer': self.instance.event.organizer.slug,
                    },
                ),
                'data-placeholder': _('No category'),
            }
        )
        self.fields['category'].widget.choices = self.fields['category'].choices

    def clean(self):
        d = super().clean()
        if d['issue_giftcard']:
            if d['tax_rule'] and d['tax_rule'].rate > 0:
                self.add_error(
                    'tax_rule',
                    _(
                        'Gift card products should not be associated with non-zero tax rates since sales tax will be applied when the gift card is redeemed.'
                    ),
                )
            if d['admission']:
                self.add_error(
                    'admission',
                    _('Gift card products should not be admission products at the same time.'),
                )
        return d

    class Meta:
        model = Product
        localized_fields = '__all__'
        fields = [
            'category',
            'name',
            'internal_name',
            'active',
            'sales_channels',
            'admission',
            'description',
            'picture',
            'default_price',
            'free_price',
            'tax_rule',
            'available_from',
            'available_until',
            'require_voucher',
            'require_approval',
            'hide_without_voucher',
            'allow_cancel',
            'allow_waitinglist',
            'max_per_order',
            'min_per_order',
            'checkin_attention',
            'generate_tickets',
            'original_price',
            'require_bundling',
            'show_quota_left',
            'hidden_if_available',
            'issue_giftcard',
        ]
        field_classes = {
            'available_from': SplitDateTimeField,
            'available_until': SplitDateTimeField,
            'hidden_if_available': SafeModelChoiceField,
        }
        widgets = {
            'available_from': SplitDateTimePickerWidget(),
            'available_until': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_available_from_0'}),
            'generate_tickets': TicketNullBooleanSelect(),
            'show_quota_left': ShowQuotaNullBooleanSelect(),
        }


class ProductVariationsFormSet(I18nFormSet):
    template = 'pretixcontrol/product/include_variations.html'
    title = _('Variations')

    def clean(self):
        super().clean()
        for f in self.forms:
            if hasattr(f, '_delete_fail'):
                f.fields['DELETE'].initial = False
                f.fields['DELETE'].disabled = True
                raise ValidationError(
                    message=_(
                        'The variation "%s" cannot be deleted because it has already been ordered by a user or '
                        'currently is in a user\'s cart. Please set the variation as "inactive" instead.'
                    ),
                    params=(str(f.instance),),
                )

    def _should_delete_form(self, form):
        should_delete = super()._should_delete_form(form)
        if (
            should_delete
            and form.instance.pk
            and (form.instance.orderposition_set.exists() or form.instance.cartposition_set.exists())
        ):
            form._delete_fail = True
            return False
        return form.cleaned_data.get(DELETION_FIELD_NAME, False)

    def _construct_form(self, i, **kwargs):
        kwargs['event'] = self.event
        return super()._construct_form(i, **kwargs)

    @property
    def empty_form(self):
        self.is_valid()
        form = self.form(
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
            use_required_attribute=False,
            locales=self.locales,
            event=self.event,
        )
        self.add_fields(form, None)
        return form


class ProductVariationForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        change_decimal_field(self.fields['default_price'], self.event.currency)

    class Meta:
        model = ProductVariation
        localized_fields = '__all__'
        fields = [
            'value',
            'active',
            'default_price',
            'original_price',
            'description',
        ]


class ProductAddOnsFormSet(I18nFormSet):
    title = _('Add-ons')
    template = 'pretixcontrol/product/include_addons.html'

    def __init__(self, *args, **kwargs):
        self.event = kwargs.get('event')
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['event'] = self.event
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        categories = set()
        for i in range(0, self.total_form_count()):
            form = self.forms[i]
            if self.can_delete:
                if self._should_delete_form(form):
                    # This form is going to be deleted so any of its errors
                    # should not cause the entire formset to be invalid.
                    try:
                        categories.remove(form.cleaned_data['addon_category'].pk)
                    except KeyError:
                        pass
                    continue

            if 'addon_category' in form.cleaned_data:
                if form.cleaned_data['addon_category'].pk in categories:
                    raise ValidationError(_('You added the same add-on category twice'))

                categories.add(form.cleaned_data['addon_category'].pk)

    @property
    def empty_form(self):
        self.is_valid()
        form = self.form(
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
            use_required_attribute=False,
            locales=self.locales,
            event=self.event,
        )
        self.add_fields(form, None)
        return form


class ProductAddOnForm(I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['addon_category'].queryset = self.event.categories.all()
        self.fields['addon_category'].widget = Select2(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.products.categories.select2',
                    kwargs={
                        'event': self.event.slug,
                        'organizer': self.event.organizer.slug,
                    },
                ),
            }
        )
        self.fields['addon_category'].widget.choices = self.fields['addon_category'].choices

    class Meta:
        model = ProductAddOn
        localized_fields = '__all__'
        fields = [
            'addon_category',
            'min_count',
            'max_count',
            'price_included',
            'multi_allowed',
        ]
        help_texts = {
            'min_count': _(
                'Be aware that setting a minimal number makes it impossible to buy this product if all '
                'available add-ons are sold out.'
            )
        }


class ProductBundleFormSet(I18nFormSet):
    template = 'pretixcontrol/product/include_bundles.html'
    title = _('Bundled products')

    def __init__(self, *args, **kwargs):
        self.event = kwargs.get('event')
        self.product = kwargs.pop('product')
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['event'] = self.event
        kwargs['product'] = self.product
        return super()._construct_form(i, **kwargs)

    @property
    def empty_form(self):
        self.is_valid()
        form = self.form(
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
            use_required_attribute=False,
            locales=self.locales,
            product=self.product,
            event=self.event,
        )
        self.add_fields(form, None)
        return form

    def clean(self):
        super().clean()
        ivs = set()
        for i in range(0, self.total_form_count()):
            form = self.forms[i]
            if self.can_delete:
                if self._should_delete_form(form):
                    # This form is going to be deleted so any of its errors
                    # should not cause the entire formset to be invalid.
                    try:
                        ivs.remove(form.cleaned_data['productvar'])
                    except KeyError:
                        pass
                    continue

            if 'productvar' in form.cleaned_data:
                if form.cleaned_data['productvar'] in ivs:
                    raise ValidationError(_('You added the same bundled product twice.'))

                ivs.add(form.cleaned_data['productvar'])


class ProductBundleForm(I18nModelForm):
    productvar = forms.ChoiceField(label=_('Bundled product'))

    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product')
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance', None)
        initial = kwargs.get('initial', {})

        if instance:
            try:
                if instance.bundled_variation:
                    initial['productvar'] = '%d-%d' % (
                        instance.bundled_product.pk,
                        instance.bundled_variation.pk,
                    )
                elif instance.bundled_product:
                    initial['productvar'] = str(instance.bundled_product.pk)
            except Product.DoesNotExist:
                pass

        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

        choices = []
        for i in self.event.products.prefetch_related('variations').all():
            pname = str(i)
            if not i.is_available():
                pname += ' ({})'.format(_('inactive'))
            variations = list(i.variations.all())

            if variations:
                for v in variations:
                    choices.append(('%d-%d' % (i.pk, v.pk), '%s – %s' % (pname, v.value)))
            else:
                choices.append((str(i.pk), '%s' % pname))
        self.fields['productvar'].choices = choices
        change_decimal_field(self.fields['designated_price'], self.event.currency)

    def clean(self):
        d = super().clean()
        if not self.cleaned_data.get('designated_price'):
            d['designated_price'] = Decimal('0.00')
            self.instance.designated_price = Decimal('0.00')

        if 'productvar' in self.cleaned_data:
            if '-' in self.cleaned_data['productvar']:
                productid, varid = self.cleaned_data['productvar'].split('-')
            else:
                productid, varid = self.cleaned_data['productvar'], None

            product = Product.objects.get(pk=productid, event=self.event)
            if varid:
                variation = ProductVariation.objects.get(pk=varid, product=product)
            else:
                variation = None

            if product == self.product:
                raise ValidationError(_('The bundled product must not be the same product as the bundling one.'))
            if product.bundles.exists():
                raise ValidationError(_('The bundled product must not have bundles on its own.'))

            self.instance.bundled_product = product
            self.instance.bundled_variation = variation

        return d

    class Meta:
        model = ProductBundle
        localized_fields = '__all__'
        fields = [
            'count',
            'designated_price',
        ]


class ProductMetaValueForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.property = kwargs.pop('property')
        super().__init__(*args, **kwargs)
        self.fields['value'].required = False
        self.fields['value'].widget.attrs['placeholder'] = self.property.default
        self.fields['value'].widget.attrs['data-typeahead-url'] = (
            reverse(
                'control:event.products.meta.typeahead',
                kwargs={
                    'organizer': self.property.event.organizer.slug,
                    'event': self.property.event.slug,
                },
            )
            + '?'
            + urlencode(
                {
                    'property': self.property.name,
                }
            )
        )

    class Meta:
        model = ProductMetaValue
        fields = ['value']
        widgets = {'value': forms.TextInput()}
