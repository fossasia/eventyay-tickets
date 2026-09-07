from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Order


class UserOrderFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        required=False,
        label=_('Event'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=_('Select an Event'),
    )
    code = forms.CharField(
        required=False,
        label=_('Order code'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by order code'),
        }),
    )
    status = forms.ChoiceField(
        required=False,
        label=_('Status'),
        choices=[
            ('', _('All statuses')),
            (Order.STATUS_PENDING, _('Pending')),
            (Order.STATUS_PAID, _('Paid')),
            (Order.STATUS_EXPIRED, _('Expired')),
            (Order.STATUS_CANCELED, _('Canceled')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    date_from = forms.DateField(
        required=False,
        label=_('Start date'),
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'class': 'form-control datepickerfield', 'type': 'text', 'autocomplete': 'off', 'placeholder': _('Start date')},
        ),
    )
    date_to = forms.DateField(
        required=False,
        label=_('End date'),
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'class': 'form-control datepickerfield', 'type': 'text', 'autocomplete': 'off', 'placeholder': _('End date')},
        ),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user from the kwargs
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if user:
            selected_event = self.get_visible_selected_event(user, request)
            event_filter = Q(orders__email__iexact=user.email)
            if selected_event:
                event_filter |= Q(pk=selected_event.pk)
            self.fields['event'].queryset = Event.objects.filter(event_filter).distinct()

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get('date_from')
        date_to = cleaned.get('date_to')
        if date_from and date_to and date_from > date_to:
            self.add_error('date_to', _('End date must be on or after start date.'))
        return cleaned

    def has_active_filters(self) -> bool:
        """True when a non-empty filter value would affect the queryset."""
        if not self.is_bound or not self.is_valid():
            return False
        cleaned = self.cleaned_data
        return bool(
            cleaned.get('event')
            or (cleaned.get('code') or '').strip()
            or cleaned.get('status')
            or cleaned.get('date_from')
            or cleaned.get('date_to')
        )

    def get_visible_selected_event(self, user, request):
        event_id = self.data.get(self.add_prefix('event')) if self.is_bound else None
        if not event_id:
            return None
        try:
            event_pk = int(event_id)
        except (TypeError, ValueError):
            return None

        event = Event.objects.select_related('organizer').filter(pk=event_pk).first()
        if not event:
            return None

        if (
            (event.live and event.is_public)
            or user.has_event_permission(event.organizer, event, request=request)
        ):
            return event
        return None


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

    def has_active_filters(self) -> bool:
        """True when a non-empty filter value would affect the queryset."""
        if not self.is_bound or not self.is_valid():
            return False
        cleaned = self.cleaned_data
        return bool(cleaned.get('event') or (cleaned.get('search') or '').strip())
