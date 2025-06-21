from django import forms
from django.conf import settings
from django.core.validators import validate_email
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.forms import I18nModelForm

from pretalx.common.forms.fields import ColorField, ImageField
from pretalx.common.forms.mixins import I18nHelpText, ReadOnlyFlag
from pretalx.common.forms.renderers import InlineFormRenderer
from pretalx.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    HtmlDateInput,
    HtmlDateTimeInput,
    TextInputWithAddon,
)
from pretalx.common.text.phrases import phrases
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
            "limit_events": EnhancedSelectMultiple,
            "limit_tracks": EnhancedSelectMultiple(color_field="color"),
        }
        field_classes = {
            "limit_tracks": SafeModelMultipleChoiceField,
        }


class TeamInviteForm(ReadOnlyFlag, forms.ModelForm):
    default_renderer = InlineFormRenderer

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
        # if we already have found errors, no need to add another one
        if not self.errors and not data.get("email") and not data.get("bulk_email"):
            raise forms.ValidationError(_("Please enter at least one email address!"))
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
        self.fields["name"].required = True
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
            widget=EnhancedSelect,
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
            (code, lang) for code, lang in settings.LANGUAGES if code in self.locales
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
            "locale": EnhancedSelect,
            "timezone": EnhancedSelect,
            "slug": TextInputWithAddon(addon_before=settings.SITE_URL + "/"),
        }


class EventWizardTimelineForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        required=False,
        help_text=_(
            "The default deadline for your Call for Papers. You can assign additional deadlines to individual session types, which will take precedence over this deadline."
        ),
        widget=HtmlDateTimeInput,
    )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            error = forms.ValidationError(phrases.orga.event_date_start_invalid)
            self.add_error("date_from", error)
        return data

    class Meta:
        model = Event
        fields = ("date_from", "date_to")
        widgets = {
            "date_from": HtmlDateInput,
            "date_to": HtmlDateInput,
        }


class EventWizardDisplayForm(forms.Form):
    primary_color = ColorField(
        label=Event._meta.get_field("primary_color").verbose_name,
        help_text=Event._meta.get_field("primary_color").help_text,
        required=False,
    )
    header_pattern = forms.ChoiceField(
        label=phrases.orga.event_header_pattern_label,
        help_text=phrases.orga.event_header_pattern_help_text,
        choices=Event.HEADER_PATTERN_CHOICES,
        required=False,
        widget=HeaderSelect,
    )

    def __init__(self, *args, user=None, locales=None, organiser=None, **kwargs):
        super().__init__(*args, **kwargs)
        logo = Event._meta.get_field("logo")
        self.fields["logo"] = ImageField(
            required=False, label=logo.verbose_name, help_text=logo.help_text
        )


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
            widget=EnhancedSelect(color_field="visible_primary_color"),
            help_text=_(
                "You can copy settings from previous events here, such as mail settings, session types, and email templates. "
                "Please check those settings once the event has been created!"
            ),
            empty_label=_("Do not copy"),
            required=False,
        )
