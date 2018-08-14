from django import forms
from django.conf import settings
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.event.models import Event, Organiser, Team, TeamInvite
from pretalx.orga.forms.widgets import HeaderSelect, MultipleLanguagesWidget


class TeamForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, organiser=None, instance=None, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        if instance and getattr(instance, 'pk', None):
            self.fields.pop('organiser')
            self.fields['limit_events'].queryset = instance.organiser.events.all()
        else:
            self.fields['organiser'].queryset = organiser

    class Meta:
        model = Team
        fields = [
            'name',
            'organiser',
            'all_events',
            'limit_events',
            'can_create_events',
            'can_change_teams',
            'can_change_organiser_settings',
            'can_change_event_settings',
            'can_change_submissions',
            'is_reviewer',
            'review_override_votes',
        ]


class TeamInviteForm(ReadOnlyFlag, forms.ModelForm):
    class Meta:
        model = TeamInvite
        fields = ('email',)


class OrganiserForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].disabled = True

    class Meta:
        model = Organiser
        fields = ('name', 'slug')


class EventWizardInitialForm(forms.Form):
    locales = forms.MultipleChoiceField(
        choices=settings.LANGUAGES,
        label=_('Use languages'),
        help_text=_('Choose all languages that your event should be available in.'),
        widget=MultipleLanguagesWidget,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organiser'] = forms.ModelChoiceField(
            label=_('Organiser'),
            queryset=Organiser.objects.filter(
                id__in=user.teams.filter(can_create_events=True).values_list(
                    'organiser', flat=True
                )
            )
            if not user.is_administrator
            else Organiser.objects.all(),
            widget=forms.RadioSelect,
            empty_label=None,
            required=True,
            help_text=_(
                'The organiser running the event can copy settings from previous events and share team permissions across all or multiple events.'
            ),
        )
        if len(self.fields['organiser'].choices) == 1:
            self.fields['organiser'].initial = self.fields['organiser'].queryset.first()


class EventWizardBasicsForm(I18nModelForm):
    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        self.locales = locales
        super().__init__(*args, **kwargs, locales=locales)
        self.fields['locale'].choices = [
            (a, b) for a, b in settings.LANGUAGES if a in locales
        ]
        self.fields['slug'].help_text = _(
            'This is the address your event will be available at. Should be short, only contain lowercase letters and numbers, and must be unique. We recommend some kind of abbreviation with less than 10 characters that can be easily remembered.'
        )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Event.objects.all()
        if qs.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                _(
                    'This short name is already taken, please choose another one (or ask the owner of that event to add you to their team).'
                )
            )

        return slug.lower()

    class Meta:
        model = Event
        fields = ('name', 'slug', 'timezone', 'email', 'locale')


class EventWizardTimelineForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        required=False, help_text=_('The default deadline for your Call for Papers.')
    )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_from'].widget.attrs['class'] = 'datepickerfield'
        self.fields['date_to'].widget.attrs['class'] = 'datepickerfield'
        self.fields['date_to'].widget.attrs['data-date-after'] = '#id_date_from'
        self.fields['deadline'].widget.attrs['class'] = 'datetimepickerfield'

    class Meta:
        model = Event
        fields = ('date_from', 'date_to')


class EventWizardDisplayForm(forms.Form):
    show_on_dashboard = forms.BooleanField(
        initial=True,
        required=False,
        label=_('Show on dashboard'),
        help_text=_('Show this event on this website\'s dashboard, once it is public?'),
    )
    primary_color = forms.CharField(required=False)
    logo = forms.ImageField(
        required=False,
        help_text=_(
            'If you provide a logo image, we will by default not show your events name and date in the page header. We will show your logo with a maximal height of 120 pixels.'
        ),
    )
    display_header_pattern = forms.ChoiceField(
        label=_('Frontpage header pattern'),
        help_text=_(
            'Choose how the frontpage header banner will be styled. Pattern source: <a href="http://www.heropatterns.com/">heropatterns.com</a>, CC BY 4.0.'
        ),
        choices=(
            ('', _('Plain')),
            ('pcb', _('Circuits')),
            ('bubbles', _('Circles')),
            ('signal', _('Signal')),
            ('topo', _('Topography')),
            ('graph', _('Graph Paper')),
        ),
        required=False,
        widget=HeaderSelect,
    )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)


class EventWizardCopyForm(forms.Form):
    @staticmethod
    def copy_from_queryset(user):
        return Event.objects.filter(
            Q(
                organiser_id__in=user.teams.filter(
                    all_events=True, can_change_event_settings=True
                ).values_list('organiser', flat=True)
            )
            | Q(
                id__in=user.teams.filter(can_change_event_settings=True).values_list(
                    'limit_events__id', flat=True
                )
            )
        )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['copy_from_event'] = forms.ModelChoiceField(
            label=_('Copy configuration from'),
            queryset=EventWizardCopyForm.copy_from_queryset(user),
            widget=forms.RadioSelect,
            empty_label=_('Do not copy'),
            required=False,
        )
