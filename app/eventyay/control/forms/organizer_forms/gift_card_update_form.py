from django import forms

from eventyay.base.forms.widgets import SplitDateTimePickerWidget
from eventyay.base.models.giftcards import GiftCard
from eventyay.control.forms import SplitDateTimeField


class GiftCardUpdateForm(forms.ModelForm):
    class Meta:
        model = GiftCard
        fields = ['expires', 'conditions']
        field_classes = {'expires': SplitDateTimeField}
        widgets = {
            'expires': SplitDateTimePickerWidget,
            'conditions': forms.Textarea(attrs={'rows': 2}),
        }
