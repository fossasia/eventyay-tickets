from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from eventyay.api.serializers.event import MetaDataField
from eventyay.api.serializers.fields import UploadedFileField
from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.base.models import (
    Product,
    ProductAddOn,
    ProductBundle,
    ProductCategory,
    ProductMetaValue,
    ProductVariation,
    Question,
    QuestionOption,
    Quota,
)


class InlineProductVariationSerializer(I18nAwareModelSerializer):
    price = serializers.DecimalField(read_only=True, decimal_places=2, max_digits=10, coerce_to_string=True)

    class Meta:
        model = ProductVariation
        fields = (
            'id',
            'value',
            'active',
            'description',
            'position',
            'default_price',
            'price',
            'original_price',
        )


class ProductVariationSerializer(I18nAwareModelSerializer):
    price = serializers.DecimalField(read_only=True, decimal_places=2, max_digits=10, coerce_to_string=True)

    class Meta:
        model = ProductVariation
        fields = (
            'id',
            'value',
            'active',
            'description',
            'position',
            'default_price',
            'price',
            'original_price',
        )


class InlineProductBundleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBundle
        fields = ('bundled_product', 'bundled_variation', 'count', 'designated_price')


class InlineProductAddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAddOn
        fields = (
            'addon_category',
            'min_count',
            'max_count',
            'position',
            'price_included',
            'multi_allowed',
        )


class ProductBundleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBundle
        fields = (
            'id',
            'bundled_product',
            'bundled_variation',
            'count',
            'designated_price',
        )

    def validate(self, data):
        data = super().validate(data)
        event = self.context['event']

        full_data = self.to_internal_value(self.to_representation(self.instance)) if self.instance else {}
        full_data.update(data)

        ProductBundle.clean_productvar(event, full_data.get('bundled_product'), full_data.get('bundled_variation'))

        product = self.context['product']
        if product == full_data.get('bundled_product'):
            raise ValidationError(_('The bundled product must not be the same product as the bundling one.'))
        if full_data.get('bundled_product'):
            if full_data['bundled_product'].bundles.exists():
                raise ValidationError(_('The bundled product must not have bundles on its own.'))

        return data


class ProductAddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAddOn
        fields = (
            'id',
            'addon_category',
            'min_count',
            'max_count',
            'position',
            'price_included',
            'multi_allowed',
        )

    def validate(self, data):
        data = super().validate(data)

        ProductAddOn.clean_max_min_count(data.get('max_count'), data.get('min_count'))

        return data

    def validate_min_count(self, value):
        ProductAddOn.clean_min_count(value)
        return value

    def validate_max_count(self, value):
        ProductAddOn.clean_max_count(value)
        return value

    def validate_addon_category(self, value):
        ProductAddOn.clean_categories(self.context['event'], self.context['product'], self.instance, value)
        return value


class ProductTaxRateField(serializers.Field):
    def to_representation(self, i):
        if i.tax_rule:
            return str(Decimal(i.tax_rule.rate))
        else:
            return str(Decimal('0.00'))


class ProductSerializer(I18nAwareModelSerializer):
    addons = InlineProductAddOnSerializer(many=True, required=False)
    bundles = InlineProductBundleSerializer(many=True, required=False)
    variations = InlineProductVariationSerializer(many=True, required=False)
    tax_rate = ProductTaxRateField(source='*', read_only=True)
    meta_data = MetaDataField(required=False, source='*')
    picture = UploadedFileField(
        required=False,
        allow_null=True,
        allowed_types=('image/png', 'image/jpeg', 'image/gif'),
        max_size=10 * 1024 * 1024,
    )

    class Meta:
        model = Product
        fields = (
            'id',
            'category',
            'name',
            'internal_name',
            'active',
            'sales_channels',
            'description',
            'default_price',
            'free_price',
            'tax_rate',
            'tax_rule',
            'admission',
            'position',
            'picture',
            'available_from',
            'available_until',
            'require_voucher',
            'hide_without_voucher',
            'allow_cancel',
            'require_bundling',
            'min_per_order',
            'max_per_order',
            'checkin_attention',
            'has_variations',
            'variations',
            'addons',
            'bundles',
            'original_price',
            'require_approval',
            'generate_tickets',
            'show_quota_left',
            'hidden_if_available',
            'allow_waitinglist',
            'issue_giftcard',
            'meta_data',
        )
        read_only_fields = ('has_variations',)

    def validate(self, data):
        data = super().validate(data)
        if self.instance and ('addons' in data or 'variations' in data or 'bundles' in data):
            raise ValidationError(
                _(
                    'Updating add-ons, bundles, or variations via PATCH/PUT is not supported. Please use the '
                    'dedicated nested endpoint.'
                )
            )

        Product.clean_per_order(data.get('min_per_order'), data.get('max_per_order'))
        Product.clean_available(data.get('available_from'), data.get('available_until'))

        if data.get('issue_giftcard'):
            if data.get('tax_rule') and data.get('tax_rule').rate > 0:
                raise ValidationError(
                    _(
                        'Gift card products should not be associated with non-zero tax rates since sales tax will be '
                        'applied when the gift card is redeemed.'
                    )
                )
            if data.get('admission'):
                raise ValidationError(_('Gift card products should not be admission products at the same time.'))

        return data

    def validate_category(self, value):
        Product.clean_category(value, self.context['event'])
        return value

    def validate_tax_rule(self, value):
        Product.clean_tax_rule(value, self.context['event'])
        return value

    def validate_bundles(self, value):
        if not self.instance:
            for b_data in value:
                ProductBundle.clean_productvar(
                    self.context['event'],
                    b_data['bundled_product'],
                    b_data['bundled_variation'],
                )
        return value

    def validate_addons(self, value):
        if not self.instance:
            for addon_data in value:
                ProductAddOn.clean_categories(
                    self.context['event'],
                    None,
                    self.instance,
                    addon_data['addon_category'],
                )
                ProductAddOn.clean_min_count(addon_data['min_count'])
                ProductAddOn.clean_max_count(addon_data['max_count'])
                ProductAddOn.clean_max_min_count(addon_data['max_count'], addon_data['min_count'])
        return value

    @cached_property
    def product_meta_properties(self):
        return {p.name: p for p in self.context['request'].event.product_meta_properties.all()}

    def validate_meta_data(self, value):
        for key in value['meta_data'].keys():
            if key not in self.product_meta_properties:
                raise ValidationError(_("Product meta data property '{name}' does not exist.").format(name=key))
        return value

    @transaction.atomic
    def create(self, validated_data):
        variations_data = validated_data.pop('variations') if 'variations' in validated_data else {}
        addons_data = validated_data.pop('addons') if 'addons' in validated_data else {}
        bundles_data = validated_data.pop('bundles') if 'bundles' in validated_data else {}
        meta_data = validated_data.pop('meta_data', None)
        product = Product.objects.create(**validated_data)

        for variation_data in variations_data:
            ProductVariation.objects.create(product=product, **variation_data)
        for addon_data in addons_data:
            ProductAddOn.objects.create(base_product=product, **addon_data)
        for bundle_data in bundles_data:
            ProductBundle.objects.create(base_product=product, **bundle_data)

        # Meta data
        if meta_data is not None:
            for key, value in meta_data.items():
                ProductMetaValue.objects.create(property=self.product_meta_properties.get(key), value=value, product=product)
        return product

    def update(self, instance, validated_data):
        meta_data = validated_data.pop('meta_data', None)
        product = super().update(instance, validated_data)

        # Meta data
        if meta_data is not None:
            current = {mv.property: mv for mv in product.meta_values.select_related('property')}
            for key, value in meta_data.items():
                prop = self.product_meta_properties.get(key)
                if prop in current:
                    current[prop].value = value
                    current[prop].save()
                else:
                    product.meta_values.create(property=self.product_meta_properties.get(key), value=value)

            for prop, current_object in current.items():
                if prop.name not in meta_data:
                    current_object.delete()

        return product


class ProductCategorySerializer(I18nAwareModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ('id', 'name', 'internal_name', 'description', 'position', 'is_addon')


class QuestionOptionSerializer(I18nAwareModelSerializer):
    identifier = serializers.CharField(allow_null=True)

    class Meta:
        model = QuestionOption
        fields = ('id', 'identifier', 'answer', 'position')

    def validate_identifier(self, value):
        QuestionOption.clean_identifier(self.context['event'], value, self.instance)
        return value


class InlineQuestionOptionSerializer(I18nAwareModelSerializer):
    identifier = serializers.CharField(allow_null=True)

    class Meta:
        model = QuestionOption
        fields = ('id', 'identifier', 'answer', 'position')


class LegacyDependencyValueField(serializers.CharField):
    def to_representation(self, obj):
        return obj[0] if obj else None

    def to_internal_value(self, data):
        return [data] if data else []


class QuestionSerializer(I18nAwareModelSerializer):
    options = InlineQuestionOptionSerializer(many=True, required=False)
    identifier = serializers.CharField(allow_null=True)
    dependency_value = LegacyDependencyValueField(source='dependency_values', required=False, allow_null=True)

    class Meta:
        model = Question
        fields = (
            'id',
            'question',
            'type',
            'required',
            'products',
            'options',
            'position',
            'ask_during_checkin',
            'identifier',
            'dependency_question',
            'dependency_values',
            'hidden',
            'dependency_value',
            'print_on_invoice',
            'help_text',
            'valid_number_min',
            'valid_number_max',
            'valid_date_min',
            'valid_date_max',
            'valid_datetime_min',
            'valid_datetime_max',
        )

    def validate_identifier(self, value):
        Question._clean_identifier(self.context['event'], value, self.instance)
        return value

    def validate_dependency_question(self, value):
        if value:
            if value.type not in (
                Question.TYPE_CHOICE,
                Question.TYPE_BOOLEAN,
                Question.TYPE_CHOICE_MULTIPLE,
            ):
                raise ValidationError('Question dependencies can only be set to boolean or choice questions.')
            if value == self.instance:
                raise ValidationError('A question cannot depend on itself.')
        return value

    def validate(self, data):
        data = super().validate(data)
        if self.instance and 'options' in data:
            raise ValidationError(
                _('Updating options via PATCH/PUT is not supported. Please use the dedicated nested endpoint.')
            )

        event = self.context['event']

        full_data = self.to_internal_value(self.to_representation(self.instance)) if self.instance else {}
        full_data.update(data)

        if full_data.get('ask_during_checkin') and full_data.get('dependency_question'):
            raise ValidationError('Dependencies are not supported during check-in.')

        dep = full_data.get('dependency_question')
        if dep:
            if dep.ask_during_checkin:
                raise ValidationError(_('Question cannot depend on a question asked during check-in.'))

            seen_ids = {self.instance.pk} if self.instance else set()
            while dep:
                if dep.pk in seen_ids:
                    raise ValidationError(_('Circular dependency between questions detected.'))
                seen_ids.add(dep.pk)
                dep = dep.dependency_question

        if full_data.get('ask_during_checkin') and full_data.get('type') in Question.ASK_DURING_CHECKIN_UNSUPPORTED:
            raise ValidationError(_('This type of question cannot be asked during check-in.'))

        Question.clean_products(event, full_data.get('products'))
        return data

    def validate_options(self, value):
        if not self.instance:
            known = []
            for opt_data in value:
                if opt_data.get('identifier'):
                    QuestionOption.clean_identifier(
                        self.context['event'],
                        opt_data.get('identifier'),
                        self.instance,
                        known,
                    )
                    known.append(opt_data.get('identifier'))
        return value

    @transaction.atomic
    def create(self, validated_data):
        options_data = validated_data.pop('options') if 'options' in validated_data else []
        products = validated_data.pop('products')

        question = Question.objects.create(**validated_data)
        question.products.set(products)
        for opt_data in options_data:
            QuestionOption.objects.create(question=question, **opt_data)
        return question


class QuotaSerializer(I18nAwareModelSerializer):
    class Meta:
        model = Quota
        fields = (
            'id',
            'name',
            'size',
            'products',
            'variations',
            'subevent',
            'closed',
            'close_when_sold_out',
            'release_after_exit',
        )

    def validate(self, data):
        data = super().validate(data)
        event = self.context['event']

        full_data = self.to_internal_value(self.to_representation(self.instance)) if self.instance else {}
        full_data.update(data)

        Quota.clean_variations(full_data.get('products'), full_data.get('variations'))
        Quota.clean_products(event, full_data.get('products'), full_data.get('variations'))
        Quota.clean_subevent(event, full_data.get('subevent'))

        return data
