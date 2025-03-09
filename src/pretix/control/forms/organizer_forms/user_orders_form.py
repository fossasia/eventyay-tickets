from django import forms

from pretix.base.models import Event


class UserOrderFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Event",
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select an Event",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        if user:
            # Query distinct events based on the user's orders
            events = Event.objects.filter(orders__email__iexact=user.email).distinct()
            self.fields["event"].queryset = events
