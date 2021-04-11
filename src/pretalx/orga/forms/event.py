import socket
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import F, Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelMultipleChoiceField
from hierarkey.forms import HierarkeyForm
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.css import validate_css
from pretalx.common.forms.fields import ImageField
from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.event.models.event import Event, Event_SettingsStore
from pretalx.orga.forms.widgets import HeaderSelect, MultipleLanguagesWidget
from pretalx.submission.models import ReviewPhase, ReviewScore, ReviewScoreCategory

ENCRYPTED_PASSWORD_PLACEHOLDER = "*******"


class EventForm(ReadOnlyFlag, I18nModelForm):
    locales = forms.MultipleChoiceField(
        label=_("Active languages"),
        choices=[],
        widget=MultipleLanguagesWidget,
        help_text=_(
            "Users will be able to use pretalx in these languages, and you will be able to provide all texts in these"
            " languages. If you don't provide a text in the language a user selects, it will be shown in your event's"
            " default language instead."
        ),
    )
    logo = ImageField(
        required=False,
        label="",
        help_text=_(
            "If you provide a logo image, we will by default not show your event's name and date in the page header. "
            "We will show your logo in its full size if possible, scaled down to the full header width."
        ),
    )
    header_image = ImageField(
        required=False,
        label="",
        help_text=_(
            "If you provide a header image, it will be displayed instead of your event's color and/or header pattern "
            "on top of all event pages. It will be center-aligned, so when the window shrinks, the center parts will "
            "continue to be displayed, and not stretched."
        ),
    )
    custom_css_text = forms.CharField(
        required=False,
        widget=forms.Textarea(),
        label="",
        help_text=_("You can type in your CSS instead of uploading it, too."),
    )

    def __init__(self, *args, **kwargs):
        self.is_administrator = kwargs.pop("is_administrator", False)
        super().__init__(*args, **kwargs)
        self.initial["locales"] = self.instance.locale_array.split(",")
        year = str(now().year)
        self.fields["name"].widget.attrs["placeholder"] = (
            _("The name of your conference, e.g. My Conference") + " " + year
        )
        self.fields["slug"].help_text = _(
            "Please contact your administrator if you need to change the short name of your event."
        )
        self.fields["primary_color"].widget.attrs["placeholder"] = _(
            "A color hex value, e.g. #ab01de"
        )
        self.fields["primary_color"].widget.attrs["class"] = "colorpickerfield"
        self.fields["slug"].disabled = True
        self.fields["date_to"].help_text = _(
            "Any sessions you have scheduled already will be moved if you change the event dates. You will have to release a new schedule version to notify all speakers."
        )
        self.fields["locales"].choices = [
            choice
            for choice in settings.LANGUAGES
            if settings.LANGUAGES_INFORMATION[choice[0]].get("visible", True)
            or choice[0] in self.instance.plugin_locales
        ]

    def clean_custom_css(self):
        if self.cleaned_data.get("custom_css") or self.files.get("custom_css"):
            css = self.cleaned_data["custom_css"] or self.files["custom_css"]
            if self.is_administrator:
                return css
            try:
                validate_css(css.read())
                return css
            except IsADirectoryError:
                self.instance.custom_css = None
                self.instance.save(update_fields=["custom_css"])
        else:
            self.instance.custom_css = None
            self.instance.save(update_fields=["custom_css"])
        return None

    def clean_custom_css_text(self):
        css = self.cleaned_data.get("custom_css_text").strip()
        if not css or self.is_administrator:
            return css
        validate_css(css)
        return css

    def clean(self):
        data = super().clean()
        if data.get("locale") not in data.get("locales", []):
            error = forms.ValidationError(
                _("Your default language needs to be one of your active languages."),
            )
            self.add_error("locale", error)
        return data

    def save(self, *args, **kwargs):
        self.instance.locale_array = ",".join(self.cleaned_data["locales"])
        if any(key in self.changed_data for key in ("date_from", "date_to")):
            self.change_dates()
        result = super().save(*args, **kwargs)
        css_text = self.cleaned_data["custom_css_text"]
        if css_text:
            self.instance.custom_css.save(
                self.instance.slug + ".css", ContentFile(css_text)
            )
        return result

    def change_dates(self):
        """Changes dates of current WIP slots, or deschedules them."""
        from pretalx.schedule.models import Availability

        old_instance = Event.objects.get(pk=self.instance.pk)
        if not self.instance.wip_schedule.talks.filter(start__isnull=False).exists():
            return
        new_date_from = self.cleaned_data["date_from"]
        new_date_to = self.cleaned_data["date_to"]
        start_delta = new_date_from - old_instance.date_from
        end_delta = new_date_to - old_instance.date_to
        shortened = (new_date_to - new_date_from) < (
            old_instance.date_to - old_instance.date_from
        )

        if start_delta and end_delta:
            # The event was moved, and we will move all talks with it.
            for key in ("start", "end"):
                filt = {f"{key}__isnull": False}
                update = {key: F(key) + start_delta}
                self.instance.wip_schedule.talks.filter(**filt).update(**update)
                Availability.objects.filter(event=self.instance).filter(**filt).update(
                    **update
                )

        # Otherwise, the event got longer, no need to do anything.
        # We *could* move all talks towards the new start date, but I'm
        # not convinced that this is the actual use case.
        # I think it's more likely that people add a new day to the start.
        if shortened:
            # The event was shortened, de-schedule all talks outside the range
            self.instance.wip_schedule.talks.filter(
                Q(start__date__gt=new_date_to) | Q(start__date__lt=new_date_from),
            ).update(start=None, end=None, room=None)
            Availability.objects.filter(
                Q(end__date__gt=new_date_to) | Q(start__date__lt=new_date_from),
                event=self.instance.event,
            ).delete()

    class Meta:
        model = Event
        fields = [
            "name",
            "slug",
            "date_from",
            "date_to",
            "timezone",
            "email",
            "locale",
            "primary_color",
            "custom_css",
            "logo",
            "header_image",
            "landing_page_text",
            "featured_sessions_text",
        ]
        widgets = {
            "date_from": forms.DateInput(attrs={"class": "datepickerfield"}),
            "date_to": forms.DateInput(
                attrs={"class": "datepickerfield", "data-date-after": "#id_date_from"}
            ),
        }


class EventSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):

    custom_domain = forms.URLField(
        label=_("Custom domain"),
        help_text=_("Enter a custom domain, such as https://my.event.example.org"),
        required=False,
    )
    imprint_url = forms.URLField(
        label=_("Imprint URL"),
        help_text=_(
            "This should point e.g. to a part of your website that has your contact details and legal information."
        ),
        required=False,
    )
    show_schedule = forms.BooleanField(
        label=_("Show schedule publicly"),
        help_text=_(
            "Unset to hide your schedule, e.g. if you want to use the HTML export exclusively."
        ),
        required=False,
    )
    schedule_display = forms.ChoiceField(
        label=_("Schedule display format"),  # TODO show small preview / icons
        choices=(
            ("proportional", _("Grid")),
            ("list", _("List")),
        ),
        required=True,
    )
    show_featured = forms.ChoiceField(
        label=_("Show featured sessions"),
        choices=(
            ("never", _("Never")),
            ("pre_schedule", _("Until the first schedule is released")),
            ("always", _("Always")),
        ),
        help_text=_("Should the sessions marked as featured be shown publicly?"),
        required=True,
    )
    export_html_on_schedule_release = forms.BooleanField(
        label=_("Generate HTML export on schedule release"),
        help_text=_(
            "The static HTML export will be provided as a .zip archive on the schedule export page."
        ),
        required=False,
    )
    html_export_url = forms.URLField(
        label=_("HTML Export URL"),
        help_text=_(
            "If you publish your schedule via the HTML export, you will want the correct absolute URL to be set in various places. "
            "Please only set this value once you have published your schedule. Should end with a slash."
        ),
        required=False,
    )
    display_header_pattern = forms.ChoiceField(
        label=_("Frontpage header pattern"),
        help_text=_(
            "Choose how the frontpage header banner will be styled if you don't upload an image. Pattern source: "
            '<a href="http://www.heropatterns.com/">heropatterns.com</a>, CC BY 4.0.'
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
    meta_noindex = forms.BooleanField(
        label=_("Ask search engines not to index the event pages"), required=False
    )

    def clean_custom_domain(self):
        data = self.cleaned_data["custom_domain"]
        if not data:
            return data
        data = data.lower()
        if data in [urlparse(settings.SITE_URL).hostname, settings.SITE_URL]:
            raise ValidationError(
                _("Please do not choose the default domain as custom event domain.")
            )
        known_domains = [
            domain.lower()
            for domain in set(
                Event_SettingsStore.objects.filter(key="custom_domain")
                .exclude(object=self.obj)
                .values_list("value", flat=True)
            )
            if domain
        ]
        parsed_domains = [urlparse(domain).hostname for domain in known_domains]
        if data in known_domains or data in parsed_domains:
            raise ValidationError(
                _("This domain is already in use for a different event.")
            )
        if not data.startswith("https://"):
            data = data[len("http://") :] if data.startswith("http://") else data
            data = "https://" + data
        data = data.rstrip("/")
        try:
            socket.gethostbyname(data[len("https://") :])
        except OSError:
            raise forms.ValidationError(
                _(
                    'The domain "{domain}" does not have a name server entry at this time. Please make sure the domain is working before configuring it here.'
                ).format(domain=data)
            )
        return data


class MailSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    mail_reply_to = forms.EmailField(
        label=_("Contact address"),
        help_text=_(
            "Reply-To address. If this setting is empty and you have no custom sender, your event email address will be used as Reply-To address."
        ),
        required=False,
    )
    mail_subject_prefix = forms.CharField(
        label=_("Mail subject prefix"),
        help_text=_(
            "The prefix will be prepended to outgoing mail subjects in [brackets]."
        ),
        required=False,
    )
    mail_signature = forms.CharField(
        label=_("Mail signature"),
        help_text=_(
            'The signature will be added to outgoing mails, preceded by "-- ".'
        ),
        required=False,
        widget=forms.Textarea,
    )
    smtp_use_custom = forms.BooleanField(
        label=_("Use custom SMTP server"),
        help_text=_(
            "All mail related to your event will be sent over the SMTP server specified by you."
        ),
        required=False,
    )
    mail_from = forms.EmailField(
        label=_("Sender address"),
        help_text=_("Sender address for outgoing emails."),
        required=False,
    )
    smtp_host = forms.CharField(label=_("Hostname"), required=False)
    smtp_port = forms.IntegerField(label=_("Port"), required=False)
    smtp_username = forms.CharField(label=_("Username"), required=False)
    smtp_password = forms.CharField(
        label=_("Password"),
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password"  # see https://bugs.chromium.org/p/chromium/issues/detail?id=370363#c7
            }
        ),
    )
    smtp_use_tls = forms.BooleanField(
        label=_("Use STARTTLS"),
        help_text=_("Commonly enabled on port 587."),
        required=False,
    )
    smtp_use_ssl = forms.BooleanField(
        label=_("Use SSL"), help_text=_("Commonly enabled on port 465."), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event = kwargs.get("obj")
        if event:
            self.fields["mail_from"].help_text += " " + _(
                "Leave empty to use the default address: {}"
            ).format(settings.MAIL_FROM)
        self.set_encrypted_password_placeholder()

    def set_encrypted_password_placeholder(self):
        if self.initial["smtp_password"]:
            self.fields["smtp_password"].widget.attrs[
                "placeholder"
            ] = ENCRYPTED_PASSWORD_PLACEHOLDER

    def clean(self):
        data = self.cleaned_data
        if not data.get("smtp_password") and data.get("smtp_username"):
            # Leave password unchanged if the username is set and the password field is empty.
            # This makes it impossible to set an empty password as long as a username is set, but
            # Python's smtplib does not support password-less schemes anyway.
            data["smtp_password"] = self.initial.get("smtp_password")

        if data.get("smtp_use_tls") and data.get("smtp_use_ssl"):
            self.add_error(
                "smtp_use_tls",
                ValidationError(
                    _(
                        "You can activate either SSL or STARTTLS security, but not both at the same time."
                    )
                ),
            )
        uses_encryption = data.get("smtp_use_tls") or data.get("smtp_use_ssl")
        localhost_names = [
            "127.0.0.1",
            "::1",
            "[::1]",
            "localhost",
            "localhost.localdomain",
        ]
        if not uses_encryption and not data.get("smtp_host") in localhost_names:
            self.add_error(
                "smtp_host",
                ValidationError(
                    _(
                        "You have to activate either SSL or STARTTLS security if you use a non-local mailserver due to data protection reasons. "
                        "Your administrator can add an instance-wide bypass. If you use this bypass, please also adjust your Privacy Policy."
                    )
                ),
            )


class ReviewSettingsForm(ReadOnlyFlag, I18nFormMixin, HierarkeyForm):
    review_score_mandatory = forms.BooleanField(
        label=_("Require a review score"), required=False
    )
    review_text_mandatory = forms.BooleanField(
        label=_("Require a review text"), required=False
    )
    review_help_text = I18nFormField(
        label=_("Help text for reviewers"),
        help_text=_(
            "This text will be shown at the top of every review, as long as reviews can be created or edited."
        )
        + " "
        + phrases.base.use_markdown,
        widget=I18nTextarea,
        required=False,
    )


class WidgetSettingsForm(HierarkeyForm):
    show_widget_if_not_public = forms.BooleanField(
        label=_("Show the widget even if the schedule is not public"),
        help_text=_(
            "Set to allow external pages to show the schedule widget, even if the schedule is not shown here using pretalx."
        ),
        required=False,
    )


class WidgetGenerationForm(forms.ModelForm):
    schedule_display = forms.ChoiceField(
        label=_("Schedule display format"),
        choices=(
            ("grid", _("Grid")),
            ("list", _("List")),
        ),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["locale"].label = _("Widget language")

    class Meta:
        model = Event
        fields = ["locale"]


class ReviewPhaseForm(I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            self.add_error(
                "end",
                forms.ValidationError(
                    _("The end of a phase has to be after its start.")
                ),
            )
        return data

    class Meta:
        model = ReviewPhase
        fields = [
            "name",
            "start",
            "end",
            "can_review",
            "can_see_speaker_names",
            "can_see_reviewer_names",
            "can_change_submission_state",
            "can_see_other_reviews",
            "can_tag_submissions",
            "speakers_can_change_submissions",
        ]
        widgets = {
            "start": forms.DateInput(attrs={"class": "datetimepickerfield"}),
            "end": forms.DateInput(attrs={"class": "datetimepickerfield"}),
        }


class ReviewScoreCategoryForm(I18nModelForm):
    new_scores = forms.CharField(required=False, initial="")

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        if not event or not event.settings.use_tracks:
            self.fields.pop("limit_tracks")
        else:
            self.fields["limit_tracks"].queryset = event.tracks.all()
        ids = self.data.get(self.prefix + "-new_scores")
        self.new_label_ids = ids.strip(",").split(",") if ids else []
        for label_id in self.new_label_ids:
            self._add_score_fields(label_id=label_id)

        self.label_fields = []
        if self.instance.id:
            scores = self.instance.scores.all()
            for score in scores:
                self.label_fields.append(
                    {
                        "score": score,
                        "label_field": score._meta.get_field("label").formfield(
                            initial=score.label
                        ),
                        "value_field": score._meta.get_field("value").formfield(
                            initial=score.value, required=False
                        ),
                    }
                )
        for score in self.label_fields:
            score_id = score["score"].id
            self.fields[f"value_{score_id}"] = score["value_field"]
            self.fields[f"label_{score_id}"] = score["label_field"]

    def _add_score_fields(self, label_id):
        self.fields[f"value_{label_id}"] = ReviewScore._meta.get_field(
            "value"
        ).formfield()
        self.fields[f"label_{label_id}"] = ReviewScore._meta.get_field(
            "label"
        ).formfield()

    def get_label_fields(self):
        for score in self.label_fields:
            score_id = score["score"].id
            yield (self[f"value_{score_id}"], self[f"label_{score_id}"])

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        for score in self.label_fields:
            score_id = score["score"].id
            if any(f"_{score_id}" in changed for changed in self.changed_data):
                value = self.cleaned_data.get(f"value_{score_id}")
                label = self.cleaned_data.get(f"label_{score_id}")
                if value is None or value == "":
                    score["score"].delete()
                else:
                    score["score"].value = value
                    score["score"].label = label
                    score["score"].save()
        for score in self.new_label_ids:
            value = self.cleaned_data.get(f"value_{score}")
            label = self.cleaned_data.get(f"label_{score}")
            if (value is not None) and label:
                ReviewScore.objects.create(
                    category=self.instance, value=value, label=label
                )
        return instance

    class Meta:
        model = ReviewScoreCategory
        fields = (
            "name",
            "is_independent",
            "weight",
            "required",
            "active",
            "limit_tracks",
        )
        field_classes = {
            "limit_tracks": SafeModelMultipleChoiceField,
        }
        widgets = {"limit_tracks": forms.CheckboxSelectMultiple}
