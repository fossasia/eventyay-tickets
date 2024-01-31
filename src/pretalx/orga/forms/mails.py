import string
from collections import defaultdict
from contextlib import suppress

from bs4 import BeautifulSoup
from django import forms
from django.db import transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.exceptions import SendMailException
from pretalx.common.mixins.forms import I18nHelpText, ReadOnlyFlag
from pretalx.common.templatetags.rich_text import rich_text
from pretalx.common.utils import language
from pretalx.mail.context import get_available_placeholders
from pretalx.mail.models import MailTemplate, QueuedMail
from pretalx.mail.placeholders import SimpleFunctionalMailTextPlaceholder
from pretalx.person.models import User
from pretalx.submission.forms import SubmissionFilterForm
from pretalx.submission.models.submission import Submission, SubmissionStates


class MailTemplateForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = getattr(self, "event", None) or event
        if self.event:
            kwargs["locales"] = self.event.locales
        super().__init__(*args, **kwargs)

    def _clean_for_placeholders(self, text, valid_placeholders):
        cleaned_data = super().clean()
        valid_placeholders = set(valid_placeholders)
        # We need to do this here, since we need to be sure about the valid placeholders first
        used_placeholders = set()
        for field in ("subject", "text"):
            value = cleaned_data.get(field)
            if not value:
                continue
            for lang in value.data.values():
                used_placeholders |= {
                    v[1] for v in string.Formatter().parse(lang) if v[1]
                }
        return used_placeholders - valid_placeholders

    def get_valid_placeholders(self, **kwargs):
        kwargs = ["event", "submission", "user", "slot"]
        valid_placeholders = {}

        if self.instance and self.instance.id:
            if self.instance == self.event.update_template:
                kwargs = ["event", "user"]
            elif self.instance == self.event.question_template:
                valid_placeholders["questions"] = SimpleFunctionalMailTextPlaceholder(
                    "questions",
                    ["user"],
                    None,
                    _("- First missing question\n- Second missing question"),
                    _(
                        "The list of questions that the user has not answered, as bullet points"
                    ),
                )
                valid_placeholders["url"] = SimpleFunctionalMailTextPlaceholder(
                    "url",
                    ["event", "user"],
                    None,
                    "https://pretalx.example.com/democon/me/submissions/",
                    is_visible=False,
                )
                kwargs = ["event", "user"]
            elif self.instance in (
                self.event.accept_template,
                self.event.reject_template,
            ):
                kwargs.remove("slot")

        valid_placeholders.update(
            get_available_placeholders(event=self.event, kwargs=kwargs)
        )
        return valid_placeholders

    @cached_property
    def grouped_placeholders(self):
        placeholders = self.get_valid_placeholders(ignore_data=True)
        grouped = defaultdict(list)
        specificity = ["slot", "submission", "user", "event", "other"]
        for placeholder in placeholders.values():
            if not placeholder.is_visible:
                continue
            placeholder.rendered_sample = placeholder.render_sample(self.event)
            for arg in specificity:
                if arg in placeholder.required_context:
                    grouped[arg].append(placeholder)
                    break
            else:
                grouped["other"].append(placeholder)
        return grouped

    def clean_text(self):
        text = self.cleaned_data["text"]
        valid_placeholders = self.get_valid_placeholders()
        try:
            warnings = self._clean_for_placeholders(text, valid_placeholders.keys())
        except Exception:
            raise forms.ValidationError(
                _(
                    "Invalid email template! "
                    "Please check that you don't have stray { or } somewhere, "
                    "and that there are no spaces inside the {} blocks."
                )
            )
        if warnings:
            warnings = ", ".join("{" + w + "}" for w in warnings)
            raise forms.ValidationError(str(_("Unknown placeholder!")) + " " + warnings)

        for locale in self.event.locales:
            with language(locale):
                message = text.localize(locale)
                preview_text = rich_text(
                    message.format_map(
                        {
                            key: value.render_sample(self.event)
                            for key, value in valid_placeholders.items()
                        }
                    )
                )
                doc = BeautifulSoup(preview_text, "lxml")
                for link in doc.findAll("a"):
                    if link.attrs.get("href") in [None, "", "http://", "https://"]:
                        raise forms.ValidationError(
                            _(
                                "You have an empty link in your email, labeled “{text}”!"
                            ).format(text=link.text)
                        )
        return text

    class Meta:
        model = MailTemplate
        fields = ["subject", "text", "reply_to", "bcc"]


class DraftRemindersForm(MailTemplateForm):
    def get_valid_placeholders(self):
        kwargs = ["event", "submission", "user"]
        return get_available_placeholders(event=self.event, kwargs=kwargs)

    def save(self, *args, **kwargs):
        template = self.instance
        submissions = Submission.all_objects.filter(
            state=SubmissionStates.DRAFT, event=self.event
        )
        mail_count = 0
        for submission in submissions:
            for user in submission.speakers.all():
                template.to_mail(
                    user=user,
                    event=self.event,
                    locale=submission.get_email_locale(user.locale),
                    context_kwargs={"submission": submission, "user": user},
                    skip_queue=True,
                    commit=False,
                )
                mail_count += 1

        return mail_count

    class Meta:
        model = MailTemplate
        fields = ["subject", "text"]


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
                {a.strip().lower() for a in (obj.to or "").split(",") if a.strip()}
            )
            found_addresses = []
            for address in addresses:
                user = User.objects.filter(email__iexact=address).first()
                if user:
                    obj.to_users.add(user)
                    found_addresses.append(address)
            addresses = set(addresses) - set(found_addresses)
            addresses = ",".join(addresses) if addresses else ""
            obj.to = addresses
            obj.save()
        return obj

    class Meta:
        model = QueuedMail
        fields = ["to", "to_users", "reply_to", "cc", "bcc", "subject", "text"]
        widgets = {"to_users": forms.SelectMultiple(attrs={"class": "select2"})}


class WriteMailBaseForm(MailTemplateForm):
    skip_queue = forms.BooleanField(
        label=_("Send immediately"),
        required=False,
        help_text=_(
            "If you check this, the emails will be sent immediately, instead of being put in the outbox."
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        valid_placeholders = self.get_valid_placeholders().keys()
        self.warnings = self._clean_for_placeholders(
            cleaned_data.get("subject", ""), valid_placeholders
        ) | self._clean_for_placeholders(
            cleaned_data.get("text", ""), valid_placeholders
        )
        return cleaned_data


class WriteTeamsMailForm(WriteMailBaseForm):
    recipients = forms.MultipleChoiceField(
        label=_("Teams"),
        required=False,
        widget=forms.SelectMultiple(
            attrs={"class": "select2", "title": _("Recipient groups")}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Placing reviewer emails in the outbox would lead to a **ton** of permission
        # issues: who is allowed to see them, who to edit/send them, etc.
        self.fields.pop("skip_queue")

        reviewer_teams = self.event.teams.filter(is_reviewer=True)
        other_teams = self.event.teams.exclude(is_reviewer=True)
        if reviewer_teams and other_teams:
            self.fields["recipients"].choices = [
                (
                    _("Reviewers"),
                    [(team.pk, team.name) for team in reviewer_teams],
                ),
                (
                    _("Other teams"),
                    [(team.pk, team.name) for team in other_teams],
                ),
            ]
        else:
            self.fields["recipients"].choices = [
                (team.pk, team.name) for team in self.event.teams.all()
            ]

    def get_valid_placeholders(self, **kwargs):
        return get_available_placeholders(event=self.event, kwargs=["event", "user"])

    def get_recipients(self):
        recipients = self.cleaned_data.get("recipients")
        teams = self.event.teams.all().filter(pk__in=recipients)
        return User.objects.filter(is_active=True, teams__in=teams)

    @transaction.atomic
    def save(self):
        self.instance.event = self.event
        self.instance.is_auto_created = True
        template = super().save()
        result = []
        users = self.get_recipients()
        for user in users:
            # This happens when there are template errors
            with suppress(SendMailException):
                result.append(
                    template.to_mail(
                        user=user,
                        event=self.event,
                        locale=user.locale,
                        context_kwargs={"user": user, "event": self.event},
                        skip_queue=True,
                        commit=False,
                    )
                )
        return result


class WriteSessionMailForm(SubmissionFilterForm, WriteMailBaseForm):
    submissions = forms.MultipleChoiceField(
        required=False,
        label=_("Proposals"),
        help_text=_(
            "Select proposals that should receive the email regardless of the other filters."
        ),
        widget=forms.SelectMultiple(attrs={"class": "select2"}),
    )
    speakers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label=_("Speakers"),
        help_text=_(
            "Select speakers that should receive the email regardless of the other filters."
        ),
        widget=forms.SelectMultiple(attrs={"class": "select2"}),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        initial = kwargs.get("initial", {})
        self.filter_search = initial.get("q")
        question = initial.get("question")
        if question:
            self.filter_question = (
                self.event.questions.all().filter(pk=question).first()
            )
            if self.filter_question:
                self.filter_option = self.filter_question.options.filter(
                    pk=initial.get("option")
                ).first()
                self.filter_answer = initial.get("answer")
                self.filter_unanswered = initial.get("unanswered")
        self.fields["submissions"].choices = [
            (sub.code, sub.title)
            for sub in self.event.submissions.all().order_by("title")
        ]
        self.fields["speakers"].queryset = self.event.submitters.all().order_by("name")
        if len(self.event.locales) > 1:
            self.fields["subject"].help_text = _(
                "If you provide only one language, that language will be used for all emails. If you provide multiple languages, the best fit for each speaker will be used."
            )
        self.warnings = []

    def get_valid_placeholders(self, ignore_data=False):
        kwargs = ["event", "user", "submission", "slot"]
        if getattr(self, "cleaned_data", None) and not ignore_data:
            if self.cleaned_data.get("speakers"):
                kwargs.remove("submission")
                kwargs.remove("slot")
        return get_available_placeholders(event=self.event, kwargs=kwargs)

    def get_recipients(self):
        added_submissions = self.cleaned_data.get("submissions")
        added_speakers = self.cleaned_data.get("speakers")
        if (added_submissions or added_speakers) and all(
            not self.cleaned_data.get(key)
            for key in (
                "state",
                "submission_type",
                "content_locale",
                "track",
                "tags",
                "question",
            )
        ):
            # If no filters have been selected, but specific submissions or speakers,
            # we will assume the users meant to send emails to only those selected,
            # not to all proposals.
            submissions = self.event.submissions.none()
        else:
            submissions = (
                self.filter_queryset(self.event.submissions)
                .select_related("track", "submission_type", "event")
                .prefetch_related("speakers")
            )

        if added_submissions:
            specific_submissions = (
                self.event.submissions.filter(code__in=added_submissions)
                .select_related("track", "submission_type", "event")
                .prefetch_related("speakers")
            )
            submissions = submissions | specific_submissions

        result = []
        for submission in submissions:
            for slot in submission.current_slots or []:
                for speaker in submission.speakers.all():
                    result.append(
                        {
                            "submission": submission,
                            "slot": slot,
                            "user": speaker,
                        }
                    )
            else:
                for speaker in submission.speakers.all():
                    result.append(
                        {
                            "submission": submission,
                            "user": speaker,
                        }
                    )
        if added_speakers:
            for user in added_speakers:
                result.append({"user": user})
        return result

    def clean_question(self):
        return getattr(self, "filter_question", None)

    def clean_option(self):
        return getattr(self, "filter_option", None)

    def clean_answer(self):
        return getattr(self, "filter_answer", None)

    def clean_unanswered(self):
        return getattr(self, "filter_unanswered", None)

    def clean_q(self):
        return getattr(self, "filter_search", None)

    @transaction.atomic
    def save(self):
        self.instance.event = self.event
        self.instance.is_auto_created = True
        template = super().save()

        mails_by_user = defaultdict(list)
        contexts = self.get_recipients()
        for context in contexts:
            with suppress(
                SendMailException
            ):  # This happens when there are template errors
                locale = context["user"].locale
                if submission := context.get("submission"):
                    locale = submission.get_email_locale(context["user"].locale)
                mail = template.to_mail(
                    user=None,
                    event=self.event,
                    locale=locale,
                    context_kwargs=context,
                    commit=False,
                    allow_empty_address=True,
                )
                mails_by_user[context["user"]].append(mail)

        result = []
        for user, user_mails in mails_by_user.items():
            # Deduplicate emails: we don't want speakers to receive the same
            # email twice, just because they have multiple submissions.
            mail_dict = {m.subject + m.text: m for m in user_mails}
            # Now we can create the emails and add the speakers to them
            for mail in mail_dict.values():
                mail.save()
                mail.to_users.add(user)
                result.append(mail)
        if self.cleaned_data.get("skip_queue"):
            for mail in result:
                mail.send()
        return result
