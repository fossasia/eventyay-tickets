from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event


class UserOrderFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label=_('Event'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=_('Select an Event'),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        if user:
            # Query distinct events based on the user's orders
            events = Event.objects.filter(orders__email__iexact=user.email).distinct()
            self.fields['event'].queryset = events


class SessionsFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        required=False,
        label=_('Event'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=_('Select an Event'),
    )

    search = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by session name')})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        if user:
            # Query distinct events based on the user's proposals
            events = Event.objects.filter(submissions__speakers__email__iexact=user.email).distinct()
            self.fields['event'].queryset = events
