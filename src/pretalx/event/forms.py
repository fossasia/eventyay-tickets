from django import forms
from django.conf import settings
from django.core.validators import validate_email
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.forms import I18nModelForm

from pretalx.common.forms.fields import ImageField
from pretalx.common.mixins.forms import I18nHelpText, ReadOnlyFlag
from pretalx.event.models import Event, Organiser, Team, TeamInvite
from pretalx.orga.forms.widgets import HeaderSelect, MultipleLanguagesWidget
from pretalx.submission.models import Track


class TeamForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    @scopes_disabled()
    def __init__(self, *args, organiser=None, instance=None, **kwargs):
        self.organiser = organiser
        super().__init__(*args, instance=instance, **kwargs)
        is_updating = instance and getattr(instance, "pk", None)
        if is_updating:
            self.fields["limit_events"].queryset = instance.organiser.events.all()
        else:
            self.fields["limit_events"].queryset = organiser.events.all()
        if is_updating and not instance.all_events and instance.limit_events.count():
            self.fields["limit_tracks"].queryset = Track.objects.filter(
                event__in=instance.limit_events.all()
            )
        else:
            self.fields["limit_tracks"].queryset = Track.objects.filter(
                event__organiser=organiser
            ).order_by("-event__date_from", "name")

    @scopes_disabled()
    def save(self, *args, **kwargs):
        self.instance.organiser = self.organiser
        return super().save(*args, **kwargs)

    def clean(self):
        data = super().clean()
        all_events = data.get("all_events")
        limit_events = data.get("limit_events")
        if not all_events and not limit_events:
            error = forms.ValidationError(
                _(
                    "Please either pick some events for this team, or grant access to all your events!"
                )
            )
            self.add_error("limit_events", error)
        permissions = (
            "can_create_events",
            "can_change_teams",
            "can_change_organiser_settings",
            "can_change_event_settings",
            "can_change_submissions",
            "is_reviewer",
        )
        if not any(data.get(permission) for permission in permissions):
            error = forms.ValidationError(
                _("Please pick at least one permission for this team!")
            )
            self.add_error(None, error)
        return data

    class Meta:
        model = Team
        fields = [
            "name",
            "all_events",
            "limit_events",
            "can_create_events",
            "can_change_teams",
            "can_change_organiser_settings",
            "can_change_event_settings",
            "can_change_submissions",
            "is_reviewer",
            "force_hide_speaker_names",
            "limit_tracks",
        ]
        widgets = {
            "limit_events": forms.SelectMultiple(attrs={"class": "select2"}),
            "limit_tracks": forms.SelectMultiple(attrs={"class": "select2"}),
        }
        field_classes = {
            "limit_tracks": SafeModelMultipleChoiceField,
        }


class TeamInviteForm(ReadOnlyFlag, forms.ModelForm):
    bulk_email = forms.CharField(
        label=_("Email addresses"),
        help_text=_("Enter one email address per line."),
        widget=forms.Textarea(attrs={"rows": 5}),
        required=False,
    )

    def clean_bulk_email(self):
        data = self.cleaned_data["bulk_email"]
        if not data:
            return []
        result = []
        for email in data.split("\n"):
            email = email.strip()
            try:
                validate_email(email)
                result.append(email)
            except forms.ValidationError:
                self.add_error(
                    "bulk_email",
                    forms.ValidationError(
                        _("“%(email)s” is not a valid email address."),
                        params={"email": email},
                    ),
                )
        return result

    def clean(self):
        data = super().clean()
        if not self.errors:
            # if we already have found errors, no need to add another one
            if not data.get("email") and not data.get("bulk_email"):
                raise forms.ValidationError(
                    _("Please enter at least one email address!")
                )
        return data

    def save(self, team):
        if emails := self.cleaned_data.get("bulk_email"):
            invites = TeamInvite.objects.bulk_create(
                [TeamInvite(team=team, email=email) for email in emails]
            )
        else:
            self.instance.team = team
            invites = [super().save()]
        for invite in invites:
            invite.send()
        return invites

    class Meta:
        model = TeamInvite
        fields = ("email",)


class OrganiserForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, **kwargs):
        kwargs["locales"] = "en"
        super().__init__(*args, **kwargs)

        if kwargs.get("instance"):
            self.fields["slug"].disabled = True

    class Meta:
        model = Organiser
        fields = ("name", "slug")


class EventWizardInitialForm(forms.Form):
    locales = forms.MultipleChoiceField(
        choices=settings.LANGUAGES,
        label=_("Use languages"),
        help_text=_("Choose all languages that your event should be available in."),
        widget=MultipleLanguagesWidget,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organiser"] = forms.ModelChoiceField(
            label=_("Organiser"),
            queryset=(
                Organiser.objects.filter(
                    id__in=user.teams.filter(can_create_events=True).values_list(
                        "organiser", flat=True
                    )
                )
                if not user.is_administrator
                else Organiser.objects.all()
            ),
            widget=forms.Select(attrs={"class": "select2"}),
            empty_label=None,
            required=True,
            help_text=_(
                "The organiser running the event can copy settings from previous events and share team permissions across all or multiple events."
            ),
        )
        self.fields["organiser"].initial = self.fields["organiser"].queryset.first()


class EventWizardBasicsForm(I18nHelpText, I18nModelForm):
    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        self.locales = locales or []
        super().__init__(*args, **kwargs, locales=locales)
        self.fields["locale"].choices = [
            (a, b) for a, b in settings.LANGUAGES if a in self.locales
        ]
        self.fields["slug"].help_text = (
            str(
                _(
                    "This is the address your event will be available at. "
                    "Should be short, only contain lowercase letters and numbers, and must be unique. "
                    "We recommend some kind of abbreviation with less than 30 characters that can be easily remembered."
                )
            )
            + " <strong>"
            + str(_("You cannot change the slug later on!"))
            + "</strong>"
        )

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        qs = Event.objects.all()
        if qs.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                _(
                    "This short name is already taken, please choose another one (or ask the owner of that event to add you to their team)."
                )
            )

        return slug.lower()

    class Meta:
        model = Event
        fields = ("name", "slug", "timezone", "email", "locale")
        widgets = {
            "locale": forms.Select(attrs={"class": "select2"}),
            "timezone": forms.Select(attrs={"class": "select2"}),
        }


class EventWizardTimelineForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        required=False,
        help_text=_(
            "The default deadline for your Call for Papers. You can assign additional deadlines to individual session types, which will take precedence over this deadline."
        ),
    )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].widget.attrs["class"] = "datetimepickerfield"

    def clean(self):
        data = super().clean()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            error = forms.ValidationError(
                _("The event end cannot be before the start.")
            )
            self.add_error("date_from", error)
        return data

    class Meta:
        model = Event
        fields = ("date_from", "date_to")
        widgets = {
            "date_from": forms.DateInput(attrs={"class": "datepickerfield"}),
            "date_to": forms.DateInput(attrs={"class": "datepickerfield"}),
        }


class EventWizardDisplayForm(forms.Form):
    primary_color = forms.CharField(
        max_length=7,
        label=_("Main event colour"),
        help_text=_(
            "Provide a hex value like #00ff00 if you want to style pretalx in your event's colour scheme."
        ),
        required=False,
    )
    header_pattern = forms.ChoiceField(
        label=_("Frontpage header pattern"),
        help_text=_(
            'Choose how the frontpage header banner will be styled. Pattern source: <a href="http://www.heropatterns.com/">heropatterns.com</a>, CC BY 4.0.'
        ),
        choices=(
            ("", _("Plain")),
            ("pcb", _("Circuits")),
            ("bubbles", _("Circles")),
            ("signal", _("Signal")),
            ("topo", _("Topography")),
            ("graph", _("Graph Paper")),
        ),
        required=False,
        widget=HeaderSelect,
    )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)
        logo = Event._meta.get_field("logo")
        self.fields["logo"] = ImageField(
            required=False, label=logo.verbose_name, help_text=logo.help_text
        )
        self.fields["primary_color"].widget.attrs["class"] = "colorpickerfield"


class EventWizardCopyForm(forms.Form):
    @staticmethod
    def copy_from_queryset(user):
        return Event.objects.filter(
            Q(
                organiser_id__in=user.teams.filter(
                    all_events=True, can_change_event_settings=True
                ).values_list("organiser", flat=True)
            )
            | Q(
                id__in=user.teams.filter(can_change_event_settings=True).values_list(
                    "limit_events__id", flat=True
                )
            )
        )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["copy_from_event"] = forms.ModelChoiceField(
            label=_("Copy configuration from"),
            queryset=EventWizardCopyForm.copy_from_queryset(user),
            widget=forms.RadioSelect,
            empty_label=_("Do not copy"),
            required=False,
        )
