from django import forms
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.event.models import Organiser, Team, TeamInvite


class TeamForm(ReadOnlyFlag, I18nModelForm):

    def __init__(self, *args, user=None, instance=None, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        if instance and getattr(instance, 'pk', None):
            self.fields.pop('organiser')
        else:
            self.fields['organiser'].queryset = Organiser.objects.filter(pk__in=Team.objects.filter(members__in=[user], can_change_teams=True).values_list('organiser_id', flat=True))

    class Meta:
        model = Team
        fields = [
            'name', 'organiser', 'all_events', 'limit_events', 'can_create_events',
            'can_change_teams', 'can_change_organiser_settings',
            'can_change_event_settings', 'can_change_submissions', 'is_reviewer',
        ]


class TeamInviteForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = TeamInvite
        fields = ('email', )
