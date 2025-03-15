from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pretix.base.models.organizer import Team
from pretix.control.forms.event import SafeEventMultipleChoiceField


class TeamForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all().order_by(
            '-has_subevents', '-date_from'
        )

    class Meta:
        model = Team
        fields = [
            'name',
            'all_events',
            'limit_events',
            'can_create_events',
            'can_change_teams',
            'can_change_organizer_settings',
            'can_manage_gift_cards',
            'can_change_event_settings',
            'can_change_items',
            'can_view_orders',
            'can_change_orders',
            'can_checkin_orders',
            'can_view_vouchers',
            'can_change_vouchers',
        ]
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(
                attrs={
                    'data-inverse-dependency': '#id_all_events',
                    'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
                }
            ),
        }
        field_classes = {'limit_events': SafeEventMultipleChoiceField}

    def clean(self):
        data = super().clean()
        if self.instance.pk and not data['can_change_teams']:
            if (
                not self.instance.organizer.teams.exclude(pk=self.instance.pk)
                .filter(can_change_teams=True, members__isnull=False)
                .exists()
            ):
                raise ValidationError(
                    _(
                        'The changes could not be saved because there would be no remaining team with '
                        'the permission to change teams and permissions.'
                    )
                )

        return data
