from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.mail.context import get_context_explanation
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.person.models import User


class MailTemplateForm(ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        if event:
            kwargs["locales"] = event.locales
        super().__init__(*args, **kwargs)

    def clean_text(self):
        text = self.cleaned_data["text"]
        if self.instance and self.instance.id:
            context = None
            if self.instance == self.event.update_template:
                context = {"notifications": "test", "event_name": "test"}
            elif self.instance == self.event.question_template:
                context = {"questions": "test", "event_name": "test", "url": "test"}
            elif self.instance in self.instance.event.fixed_templates:
                context = {item["name"]: "test" for item in get_context_explanation()}
            if context:
                try:
                    for language, local_text in text.data.items():
                        local_text.format(**context)
                except KeyError as e:
                    raise forms.ValidationError(
                        ('Unknown template key: "{key}", locale: {locale}').format(
                            key=e.args[0], locale=language
                        )
                    )
        return text

    class Meta:
        model = MailTemplate
        fields = ["subject", "text", "reply_to", "bcc"]


class MailDetailForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.to_users.all().count():
            self.fields.pop("to_users")
        else:
            self.fields["to_users"].queryset = self.instance.to_users.all()
            self.fields["to_users"].required = False

    def clean(self, *args, **kwargs):
        cleaned_data = super().clean(*args, **kwargs)
        if not cleaned_data["to"] and not cleaned_data.get("to_users"):
            self.add_error(
                "to",
                forms.ValidationError(
                    _("An email needs to have at least one recipient.")
                ),
            )
        return cleaned_data

    def save(self, *args, **kwargs):
        obj = super().save(*args, **kwargs)
        if self.has_changed() and "to" in self.changed_data:
            addresses = list(
                set(a.strip().lower() for a in (obj.to or "").split(",") if a.strip())
            )
            for address in addresses:
                user = User.objects.filter(email__iexact=address).first()
                if user:
                    addresses.remove(address)
                    obj.to_users.add(user)
            addresses = ",".join(addresses) if addresses else ""
            obj.to = addresses
            obj.save()
        return obj

    class Meta:
        model = QueuedMail
        fields = ["to", "to_users", "reply_to", "cc", "bcc", "subject", "text"]
        widgets = {"to_users": forms.SelectMultiple(attrs={"class": "select2"})}


class WriteMailForm(I18nModelForm):
    recipients = forms.MultipleChoiceField(
        label=_("Recipient groups"),
        choices=(
            (
                "submitted",
                _("Everyone with proposal(s) that have not been accepted/rejected yet"),
            ),
            (
                "accepted",
                _("All accepted speakers (who have not confirmed their session yet)"),
            ),
            ("confirmed", _("All confirmed speakers")),
            ("rejected", _("All rejected speakers")),
            ("reviewers", _("All reviewers in your team")),
            ("no_slides", _("All confirmed speakers who have not uploaded slides")),
        ),
        required=False,
        widget=forms.SelectMultiple(
            attrs={"class": "select2", "title": _("Recipient groups")}
        ),
    )
    tracks = forms.MultipleChoiceField(
        label=_("All proposals in these tracks"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "select2", "title": _("Tracks")}),
        help_text=_("Leave empty to include proposals from all tracks."),
    )
    submission_types = forms.MultipleChoiceField(
        label=_("All proposals of these types"),
        required=False,
        widget=forms.SelectMultiple(
            attrs={"class": "select2", "title": _("Session types")}
        ),
        help_text=_("Leave empty to include proposals of all session types."),
    )
    submissions = forms.MultipleChoiceField(
        required=False,
        label=_("Proposals"),
        widget=forms.SelectMultiple(
            attrs={"class": "select2", "title": _("Proposals")}
        ),
        help_text=_(
            "Select proposals that should receive the email regardless of the other filters."
        ),
    )
    reply_to = forms.CharField(required=False)

    def __init__(self, event, **kwargs):
        self.event = event
        if event:
            kwargs["locales"] = event.locales
        super().__init__(**kwargs)
        self.fields["submissions"].choices = [
            (sub.code, sub.title) for sub in event.submissions.all()
        ]
        if event.settings.use_tracks and event.tracks.all().exists():
            self.fields["tracks"].choices = [
                (track.pk, track.name) for track in event.tracks.all()
            ]
        else:
            del self.fields["tracks"]
        self.fields["submission_types"].choices = [
            (submission_type.pk, submission_type.name)
            for submission_type in event.submission_types.all()
        ]
        if len(self.event.locales) > 1:
            self.fields["subject"].help_text = _(
                "If you provide only one language, that language will be used for all emails. If you provide multiple languages, the best fit for each speaker will be used."
            )
        self.fields["text"].help_text = _(
            "Please note: Placeholders will not be substituted, this is an upcoming feature. "
            "Leave no placeholders in this field."
        )

    def get_recipient_submissions(self):
        submissions = self.event.submissions.all()

        query = Q()
        submission_states = [
            s
            for s in ["submitted", "accepted", "confirmed", "rejected"]
            if s in self.cleaned_data["recipeients"]
        ]
        if submission_states:
            query = query | Q(state__in=submission_states)

        if "no_slides":
            query = query | Q(resources__isnull=True)

        filter_submissions = self.cleaned_data.get("submissions")
        if filter_submissions:
            query = query | Q(pk__in=[s.pk for s in filter_submissions])

        submissions = submissions.filter(query)

        tracks = self.cleaned_data.get("tracks")
        if tracks:
            submissions = submissions.filter(track__in=tracks)

        submission_types = self.cleaned_data.get("submission_types")
        if submission_types:
            submissions = submissions.filter(submission_type__in=submission_types)
        return submissions

    def clean(self):
        # TODO validate placeholders
        # - room/start/end are only allowed when all talks are in accepted/confirmed
        return super().clean()

    class Meta:
        model = MailTemplate
        fields = ["subject", "text"]
