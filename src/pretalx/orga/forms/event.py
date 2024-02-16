import datetime as dt
import socket
from decimal import Decimal
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import F, Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.forms import I18nFormMixin, I18nModelForm

from pretalx.common.css import validate_css
from pretalx.common.forms.fields import ImageField
from pretalx.common.mixins.forms import (
    HierarkeyMixin,
    I18nHelpText,
    JsonSubfieldMixin,
    ReadOnlyFlag,
)
from pretalx.common.phrases import phrases
from pretalx.event.models.event import Event
from pretalx.orga.forms.widgets import HeaderSelect, MultipleLanguagesWidget
from pretalx.schedule.models import Availability, TalkSlot
from pretalx.submission.models import ReviewPhase, ReviewScore, ReviewScoreCategory

ENCRYPTED_PASSWORD_PLACEHOLDER = "*******"


class EventForm(ReadOnlyFlag, I18nHelpText, JsonSubfieldMixin, I18nModelForm):
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
    content_locales = forms.MultipleChoiceField(
        label=_("Content languages"),
        choices=[],
        widget=forms.SelectMultiple(attrs={"class": "select2"}),
        help_text=_("Users will be able to submit proposals in these languages."),
    )
    custom_css_text = forms.CharField(
        required=False,
        widget=forms.Textarea(),
        label="",
        help_text=_("You can type in your CSS instead of uploading it, too."),
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
    schedule = forms.ChoiceField(
        label=_("Schedule display format"),
        choices=(
            ("grid", _("Grid")),
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
        help_text=_(
            "Marking sessions as 'featured' is a good way to show them before the first schedule release, or to highlight them once the schedule is visible."
        ),
        required=True,
    )
    use_feedback = forms.BooleanField(
        label=_("Enable anonymous feedback"),
        help_text=_(
            "Attendees will be able to send in feedback after a session is over."
        ),
        required=False,
    )
    export_html_on_release = forms.BooleanField(
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
    header_pattern = forms.ChoiceField(
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

    def __init__(self, *args, **kwargs):
        self.is_administrator = kwargs.pop("is_administrator", False)
        super().__init__(*args, **kwargs)
        self.initial["locales"] = self.instance.locale_array.split(",")
        self.initial["content_locales"] = self.instance.content_locale_array.split(",")
        year = str(now().year)
        self.fields["show_featured"].help_text = (
            str(self.fields["show_featured"].help_text)
            + " "
            + str(_("You can find the page <a {href}>here</a>.")).format(
                href=f'href="{self.instance.urls.featured}"'
            )
        )
        self.fields["name"].widget.attrs["placeholder"] = (
            _("The name of your conference, e.g. My Conference") + " " + year
        )
        if not self.is_administrator:
            self.fields["slug"].disabled = True
            self.fields["slug"].help_text = _(
                "Please contact your administrator if you need to change the short name of your event."
            )
        self.fields["primary_color"].widget.attrs["placeholder"] = _(
            "A color hex value, e.g. #ab01de"
        )
        self.fields["primary_color"].widget.attrs["class"] = "colorpickerfield"
        self.fields["date_to"].help_text = _(
            "Any sessions you have scheduled already will be moved if you change the event dates. You will have to release a new schedule version to notify all speakers."
        )
        self.fields["locales"].choices = [
            choice
            for choice in settings.LANGUAGES
            if settings.LANGUAGES_INFORMATION[choice[0]].get("visible", True)
            or choice[0] in self.instance.plugin_locales
        ]
        self.fields["content_locales"].choices = self.instance.available_content_locales

    def clean_custom_domain(self):
        data = self.cleaned_data["custom_domain"]
        if not data:
            return data
        data = data.lower()
        if data in [urlparse(settings.SITE_URL).hostname, settings.SITE_URL]:
            raise ValidationError(
                _("Please do not choose the default domain as custom event domain.")
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
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            error = forms.ValidationError(
                _("The event end cannot be before the start.")
            )
            self.add_error("date_from", error)
        if data.get("locale") not in data.get("locales", []):
            error = forms.ValidationError(
                _("Your default language needs to be one of your active languages."),
            )
            self.add_error("locale", error)
        return data

    def save(self, *args, **kwargs):
        self.instance.locale_array = ",".join(self.cleaned_data["locales"])
        self.instance.content_locale_array = ",".join(
            self.cleaned_data["content_locales"]
        )
        if any(key in self.changed_data for key in ("date_from", "date_to")):
            self.change_dates()
        if "timezone" in self.changed_data:
            self.change_timezone()
        result = super().save(*args, **kwargs)
        css_text = self.cleaned_data["custom_css_text"]
        if css_text:
            self.instance.custom_css.save(
                self.instance.slug + ".css", ContentFile(css_text)
            )
        return result

    def change_dates(self):
        """Changes dates of current WIP slots, or deschedules them."""

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
            self._move_by(start_delta)

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

    def change_timezone(self):
        """Changes times of all current wip slots, on the assumption that a
        change in timezone is usually not intentional, and people would like to
        keep the apparent time rather the absolute one."""

        old_instance = Event.objects.get(pk=self.instance.pk)
        first_slot = self.instance.wip_schedule.talks.filter(
            start__isnull=False
        ).first()
        if not first_slot:
            return

        def make_naive(moment):
            return dt.datetime(
                year=moment.year,
                month=moment.month,
                day=moment.day,
                hour=moment.hour,
                minute=moment.minute,
            )

        old_start = make_naive(first_slot.start.astimezone(old_instance.tz))
        new_start = make_naive(first_slot.start.astimezone(self.instance.tz))

        delta = old_start - new_start
        if delta:
            self._move_by(delta, past=True)

    def _move_by(self, delta, past=False):
        if past:
            talk_queryset = TalkSlot.objects.filter(schedule__event=self.instance)
        else:
            talk_queryset = self.instance.wip_schedule.talks
        for key in ("start", "end"):
            filt = {f"{key}__isnull": False}
            update = {key: F(key) + delta}
            talk_queryset.filter(**filt).update(**update)
            Availability.objects.filter(event=self.instance).filter(**filt).update(
                **update
            )

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
            "custom_domain",
            "primary_color",
            "custom_css",
            "logo",
            "header_image",
            "landing_page_text",
            "featured_sessions_text",
        ]
        field_classes = {
            "logo": ImageField,
            "header_image": ImageField,
        }
        widgets = {
            "date_from": forms.DateInput(attrs={"class": "datepickerfield"}),
            "date_to": forms.DateInput(
                attrs={"class": "datepickerfield", "data-date-after": "#id_date_from"}
            ),
            "locale": forms.Select(attrs={"class": "select2"}),
            "timezone": forms.Select(attrs={"class": "select2"}),
        }
        json_fields = {
            "imprint_url": "display_settings",
            "show_schedule": "feature_flags",
            "schedule": "display_settings",
            "show_featured": "feature_flags",
            "use_feedback": "feature_flags",
            "export_html_on_release": "feature_flags",
            "html_export_url": "display_settings",
            "header_pattern": "display_settings",
            "meta_noindex": "display_settings",
        }


class MailSettingsForm(
    ReadOnlyFlag, I18nFormMixin, I18nHelpText, JsonSubfieldMixin, forms.Form
):
    reply_to = forms.EmailField(
        label=_("Contact address"),
        help_text=_(
            "Reply-To address. If this setting is empty and you have no custom sender, your event email address will be used as Reply-To address."
        ),
        required=False,
    )
    subject_prefix = forms.CharField(
        label=_("Mail subject prefix"),
        help_text=_(
            "The prefix will be prepended to outgoing mail subjects in [brackets]."
        ),
        required=False,
    )
    signature = forms.CharField(
        label=_("Mail signature"),
        help_text=str(
            _('The signature will be added to outgoing mails, preceded by "-- ".')
        )
        + " "
        + phrases.base.use_markdown,
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
        self.set_encrypted_password_placeholder()

    def set_encrypted_password_placeholder(self):
        if self.initial.get("smtp_password"):
            self.fields["smtp_password"].widget.attrs[
                "placeholder"
            ] = ENCRYPTED_PASSWORD_PLACEHOLDER

    def clean(self):
        data = self.cleaned_data
        if not data.get("smtp_use_custom"):
            # We don't need to validate all the rest when we don't use a custom email server
            return data

        if not data.get("smtp_password") and data.get("smtp_username"):
            # Leave password unchanged if the username is set and the password field is empty.
            # This makes it impossible to set an empty password as long as a username is set, but
            # Python's smtplib does not support password-less schemes anyway.
            data["smtp_password"] = self.initial.get("smtp_password")

        if not data.get("mail_from"):
            self.add_error(
                "mail_from",
                ValidationError(
                    _(
                        "You have to provide a sender address if you use a custom SMTP server."
                    )
                ),
            )
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

    class Meta:
        json_fields = {
            "reply_to": "mail_settings",
            "subject_prefix": "mail_settings",
            "signature": "mail_settings",
            "smtp_use_custom": "mail_settings",
            "mail_from": "mail_settings",
            "smtp_host": "mail_settings",
            "smtp_port": "mail_settings",
            "smtp_username": "mail_settings",
            "smtp_password": "mail_settings",
            "smtp_use_tls": "mail_settings",
            "smtp_use_ssl": "mail_settings",
        }


class ReviewSettingsForm(
    ReadOnlyFlag,
    I18nFormMixin,
    I18nHelpText,
    HierarkeyMixin,
    JsonSubfieldMixin,
    forms.Form,
):
    score_mandatory = forms.BooleanField(
        label=_("Require a review score"), required=False
    )
    text_mandatory = forms.BooleanField(
        label=_("Require a review text"), required=False
    )
    score_format = forms.ChoiceField(
        label=_("Score display"),
        required=True,
        choices=(
            ("words_numbers", _("Text and score, e.g “Good (3)”")),
            ("numbers_words", _("Score and text, e.g “3 (good)”")),
            ("numbers", _("Just scores")),
            ("words", _("Just text")),
        ),
        initial="words_numbers",
        help_text=_(
            "This is how the score will look like on the review interface. The dashboard will always show numerical scores."
        ),
        widget=forms.RadioSelect,
    )
    aggregate_method = forms.ChoiceField(
        label=_("Score aggregation method"),
        required=True,
        choices=(("median", _("Median")), ("mean", _("Average (mean)"))),
        widget=forms.RadioSelect,
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

    class Meta:
        json_fields = {
            "score_mandatory": "review_settings",
            "text_mandatory": "review_settings",
            "aggregate_method": "review_settings",
            "score_format": "review_settings",
        }
        hierarkey_fields = ("review_help_text",)


class WidgetSettingsForm(JsonSubfieldMixin, forms.Form):
    show_widget_if_not_public = forms.BooleanField(
        label=_("Show the widget even if the schedule is not public"),
        help_text=_(
            "Set to allow external pages to show the schedule widget, even if the schedule is not shown here using pretalx."
        ),
        required=False,
    )

    class Meta:
        json_fields = {"show_widget_if_not_public": "feature_flags"}


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
        widgets = {"locale": forms.Select(attrs={"class": "select2"})}


class ReviewPhaseForm(I18nHelpText, I18nModelForm):
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
            "proposal_visibility",
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


def strip_zeroes(value):
    if not isinstance(value, Decimal):
        return value
    value = str(value)
    return Decimal(value.rstrip("0"))


class ReviewScoreCategoryForm(I18nHelpText, I18nModelForm):
    new_scores = forms.CharField(required=False, initial="")

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        if not event or not event.feature_flags["use_tracks"]:
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
                            initial=strip_zeroes(score.value), required=False
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
        widgets = {"limit_tracks": forms.SelectMultiple(attrs={"class": "select2"})}
