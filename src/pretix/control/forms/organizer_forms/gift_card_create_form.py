from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from pretix.base.forms.widgets import SplitDateTimePickerWidget
from pretix.base.models.giftcards import GiftCard
from pretix.control.forms import SplitDateTimeField


class GiftCardCreateForm(forms.ModelForm):
    value = forms.DecimalField(label=_('Gift card value'), min_value=Decimal('0.00'))

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer')
        initial = kwargs.pop('initial', {})
        initial['expires'] = self.organizer.default_gift_card_expiry
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def clean_secret(self):
        secret = self.cleaned_data.get('secret')
        exists = (
            GiftCard.objects.filter(secret__iexact=secret)
            .filter(
                Q(issuer=self.organizer)
                | Q(issuer__gift_card_collector_acceptance__collector=self.organizer)
            )
            .exists()
        )

        if exists:
            raise ValidationError(
                _(
                    'A gift card with the same secret already exists in your or an affiliated organizer account.'
                )
            )

        return secret

    class Meta:
        model = GiftCard
        fields = ['secret', 'currency', 'testmode', 'expires', 'conditions']
        field_classes = {'expires': SplitDateTimeField}
        widgets = {
            'expires': SplitDateTimePickerWidget,
            'conditions': forms.Textarea(attrs={'rows': 2}),
        }
