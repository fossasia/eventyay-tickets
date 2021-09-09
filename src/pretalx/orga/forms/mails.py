import string
from collections import defaultdict
from contextlib import suppress

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.exceptions import SendMailException
from pretalx.common.mixins.forms import I18nHelpText, ReadOnlyFlag
from pretalx.mail.context import get_available_placeholders
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.person.models import User


class MailTemplateBase(I18nHelpText, I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_placeholders = ", ".join(
            [
                "{" + f"{placeholder}" + "}"
                for placeholder in self.get_valid_placeholders()
            ]
        )
        self.fields["text"].help_text = (
            _("Available placeholders:") + " " + available_placeholders
        )
        self.fields["subject"].help_text = (
            _("Available placeholders:") + " " + available_placeholders
        )

    def _clean_for_placeholders(self, text, valid_placeholders):
        cleaned_data = super().clean()
        valid_placeholders = set(valid_placeholders)
        # We need to do this here, since we need to be sure about the valid placeholders first
        used_placeholders = set()
        for field in ("subject", "text"):
            for lang in cleaned_data[field].data.values():
                used_placeholders |= set(
                    [v[1] for v in string.Formatter().parse(lang) if v[1]]
                )
        return used_placeholders - valid_placeholders

    class Meta:
        model = MailTemplate
        fields = ["subject", "text"]


class MailTemplateForm(ReadOnlyFlag, MailTemplateBase):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        if event:
            kwargs["locales"] = event.locales
        super().__init__(*args, **kwargs)

    def get_valid_placeholders(self):
        kwargs = ["event", "submission", "user", "slot"]
        valid_placeholders = []

        if self.instance and self.instance.id:
            if self.instance == self.event.update_template:
                valid_placeholders.append("notifications")
                kwargs = ["event", "user"]
            elif self.instance == self.event.question_template:
                valid_placeholders.append("questions")
                valid_placeholders.append("url")
                kwargs = ["event", "user"]

        valid_placeholders += list(
            get_available_placeholders(event=self.event, kwargs=kwargs).keys()
        )
        return valid_placeholders

    def clean_text(self):
        text = self.cleaned_data["text"]
        valid_placeholders = self.get_valid_placeholders()
        warnings = self._clean_for_placeholders(text, valid_placeholders)
        if warnings:
            warnings = ", ".join("{" + w + "}" for w in warnings)
            raise forms.ValidationError(
                str(_("Unknown template key!")) + " " + warnings
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


class WriteMailForm(MailTemplateBase):
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
        self.warnings = []

    def get_valid_placeholders(self):
        kwargs = ["event", "submission", "user"]
        if getattr(self, "cleaned_data", None):
            recipients = self.cleaned_data.get("recipients")
            if recipients and not set(recipients) - set(["accepted", "confirmed"]):
                kwargs.append("slot")
        else:  # Not cleaned yet, we only need this for the help text
            kwargs.append("slot")
        return get_available_placeholders(event=self.event, kwargs=kwargs)

    def get_recipient_submissions(self):
        # If no recipient base groups are selected,
        submissions = self.event.submissions.all()
        submission_states = [
            s
            for s in ["submitted", "accepted", "confirmed", "rejected"]
            if s in self.cleaned_data["recipients"]
        ]
        if submission_states:
            query = Q(state__in=submission_states)
        elif "no_slides" in self.cleaned_data["recipients"]:
            query = Q(state__isnull=False)
        else:
            query = Q()
        if "no_slides" in self.cleaned_data["recipients"]:
            if submission_states:
                query = query | Q(resources__isnull=True)
            else:
                query = Q(resources__isnull=True)

        submissions = submissions.filter(query)

        tracks = self.cleaned_data.get("tracks")
        if tracks:
            submissions = submissions.filter(track__in=tracks)

        submission_types = self.cleaned_data.get("submission_types")
        if submission_types:
            submissions = submissions.filter(submission_type__in=submission_types)

        submissions = submissions.select_related(
            "track", "submission_type", "event"
        ).prefetch_related("speakers")

        # Specifically filtered-for submissions need to come last, so they can't be excluded
        filter_submissions = self.cleaned_data.get("submissions")
        if filter_submissions:
            filtered = any(
                self.cleaned_data.get(key)
                for key in ["recipients", "tracks", "submission_types"]
            )
            specific_submissions = (
                self.event.submissions.filter(code__in=filter_submissions)
                .select_related("track", "submission_type", "event")
                .prefetch_related("speakers")
            )
            if filtered:
                # If we have filtered on things already, we add our specific sessions to the existing set
                submissions = submissions.union(specific_submissions)
            else:
                # Otherwise, we assume that the user wanted *only* the specific sessions
                submissions = specific_submissions
        return submissions

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("subject"):
            raise forms.ValidationError(_("Please provide an email subject!"))
        if not cleaned_data.get("text"):
            raise forms.ValidationError(_("Please provide an email text!"))
        valid_placeholders = self.get_valid_placeholders().keys()
        self.warnings = self._clean_for_placeholders(
            cleaned_data["subject"], valid_placeholders
        ) | self._clean_for_placeholders(cleaned_data["text"], valid_placeholders)
        return cleaned_data

    @transaction.atomic
    def save(self):
        self.instance.event = self.event
        self.instance.is_auto_created = True
        template = super().save()

        submissions = self.get_recipient_submissions()
        mails_by_user = defaultdict(list)
        result = []
        # First, render all emails
        for submission in submissions:
            for speaker in submission.speakers.all():
                with suppress(
                    SendMailException
                ):  # This happens when there are template errors
                    mail = template.to_mail(
                        user=None,
                        event=self.event,
                        locale=speaker.locale,
                        context_kwargs={"submission": submission, "user": speaker},
                        commit=False,
                        allow_empty_address=True,
                    )
                    mails_by_user[speaker].append(mail)

        for user, user_mails in mails_by_user.items():
            # Second, deduplicate mails: we don't want speakers to receive the same
            # email twice, just because they have multiple submissions.
            mail_dict = {m.subject + m.text: m for m in user_mails}
            # Now we can create the emails and add the speakers to them
            for mail in mail_dict.values():
                mail.save()
                mail.to_users.add(user)
                result.append(mail)
        return result

    class Meta:
        model = MailTemplate
        fields = ["subject", "text"]
