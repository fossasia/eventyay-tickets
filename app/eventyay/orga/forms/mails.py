from collections import defaultdict
from contextlib import suppress
from datetime import timedelta

from bs4 import BeautifulSoup
from django import forms
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from eventyay.base.forms.widgets import SplitDateTimePickerWidget
from eventyay.base.models import MailTemplate, QueuedMail, Track, User
from eventyay.base.models.submission import Submission, SubmissionStates
from eventyay.common.exceptions import SendMailException
from eventyay.common.forms.fields import I18nEmailBodyFormField
from eventyay.common.forms.mixins import I18nHelpText, ReadOnlyFlag, ScheduledAtValidationMixin
from eventyay.common.forms.renderers import InlineFormRenderer, TabularFormRenderer
from eventyay.common.forms.widgets import EnhancedSelectMultiple, I18nEmailEditorWidget, SelectMultipleWithCount
from eventyay.common.language import language
from eventyay.common.text.phrases import phrases
from eventyay.control.forms import SplitDateTimeField
from eventyay.mail.context import get_available_placeholders, get_invalid_placeholders
from eventyay.submission.forms import SubmissionFilterForm


class TalkSplitDateTimePickerWidget(SplitDateTimePickerWidget):
    """Talk-specific widget that uses native HTML5 date and time inputs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_attrs = self.widgets[0].attrs.copy()
        time_attrs = self.widgets[1].attrs.copy()
        date_attrs['class'] = ' '.join(c for c in date_attrs.get('class', '').split() if c != 'datepickerfield')
        time_attrs['class'] = ' '.join(c for c in time_attrs.get('class', '').split() if c != 'timepickerfield')
        date_attrs['type'] = 'date'
        time_attrs['type'] = 'time'
        self.widgets = (
            forms.DateInput(attrs=date_attrs, format='%Y-%m-%d'),
            forms.TimeInput(attrs=time_attrs, format='%H:%M:%S'),
        )


class MailTemplateForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    default_renderer = TabularFormRenderer

    def __init__(self, *args, event=None, **kwargs):
        self.event = getattr(self, 'event', None) or event
        if self.event:
            kwargs['locales'] = self.event.locales
        super().__init__(*args, **kwargs)
        self.fields['subject'].required = True
        text_field = self.fields['text']
        placeholder_names = sorted(self.valid_placeholders.keys())
        self.fields['text'] = I18nEmailBodyFormField(
            label=text_field.label,
            help_text=text_field.help_text,
            widget=I18nEmailEditorWidget,
            widget_kwargs={'placeholders': placeholder_names},
            required=True,
            locales=self.event.locales,
        )

    def get_valid_placeholders(self, **kwargs):
        if not getattr(self.instance, 'event', None):
            self.instance.event = self.event
        return self.instance.valid_placeholders

    @cached_property
    def valid_placeholders(self):
        return self.get_valid_placeholders()

    @cached_property
    def grouped_placeholders(self):
        placeholders = self.get_valid_placeholders(ignore_data=True)
        grouped = defaultdict(list)
        specificity = ['slot', 'submission', 'user', 'event', 'other']
        for placeholder in placeholders.values():
            if not placeholder.is_visible:
                continue
            placeholder.rendered_sample = escape(placeholder.render_sample(self.event))
            for arg in specificity:
                if arg in placeholder.required_context:
                    grouped[arg].append(placeholder)
                    break
            else:
                grouped['other'].append(placeholder)
        return grouped

    def clean_subject(self):
        text = self.cleaned_data['subject']
        try:
            warnings = get_invalid_placeholders(text, self.valid_placeholders)
        except Exception:
            raise forms.ValidationError(
                _(
                    'Invalid email template! '
                    'Please check that you don’t have stray { or } somewhere, '
                    'and that there are no spaces inside the {} blocks.'
                )
            )
        if warnings:
            warnings = ', '.join('{' + warning + '}' for warning in warnings)
            raise forms.ValidationError(str(_('Unknown placeholder!')) + ' ' + warnings)
        return text

    def clean_text(self):
        text = self.cleaned_data['text']
        try:
            warnings = get_invalid_placeholders(text, self.valid_placeholders)
        except Exception:
            raise forms.ValidationError(
                _(
                    'Invalid email template! '
                    'Please check that you don’t have stray { or } somewhere, '
                    'and that there are no spaces inside the {} blocks.'
                )
            )
        if warnings:
            warnings = ', '.join('{' + warning + '}' for warning in warnings)
            raise forms.ValidationError(str(_('Unknown placeholder!')) + ' ' + warnings)

        from eventyay.base.templatetags.rich_text import compile_email_body

        for locale in self.event.locales:
            with language(locale):
                message = text.localize(locale)
                preview_text = compile_email_body(
                    message.format_map(
                        {key: escape(value.render_sample(self.event)) for key, value in self.valid_placeholders.items()}
                    )
                )
                doc = BeautifulSoup(preview_text, 'lxml')
                for link in doc.find_all('a'):
                    if link.attrs.get('href') in (None, '', 'http://', 'https://'):
                        raise forms.ValidationError(
                            _('You have an empty link in your email, labeled “{text}”!').format(text=link.text)
                        )
        return text

    class Meta:
        model = MailTemplate
        fields = ['subject', 'text', 'reply_to', 'bcc']


class DraftRemindersForm(MailTemplateForm):
    def get_valid_placeholders(self):
        kwargs = ['event', 'submission', 'user']
        return get_available_placeholders(event=self.event, kwargs=kwargs)

    def save(self, *args, **kwargs):
        template = self.instance
        submissions = Submission.all_objects.filter(state=SubmissionStates.DRAFT, event=self.event)
        mail_count = 0
        for submission in submissions:
            for user in submission.speakers.all():
                template.to_mail(
                    user=user,
                    event=self.event,
                    locale=submission.get_email_locale(user.locale),
                    context_kwargs={'submission': submission, 'user': user},
                    skip_queue=True,
                    commit=False,
                )
                mail_count += 1

        return mail_count

    class Meta:
        model = MailTemplate
        fields = ['subject', 'text']


class MailDetailForm(ScheduledAtValidationMixin, ReadOnlyFlag, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.to_users.all().count():
            self.fields.pop('to_users')
        else:
            self.fields['to_users'].queryset = User.objects.filter(
                Q(pk__in=self.instance.to_users.values_list('pk', flat=True))
                | Q(submissions__in=self.instance.event.submissions.all())
                | Q(teams__in=self.instance.event.teams.all())
            ).distinct()
            self.fields['to_users'].required = False

    def clean(self, *args, **kwargs):
        cleaned_data = super().clean(*args, **kwargs)
        if not cleaned_data['to'] and not cleaned_data.get('to_users'):
            self.add_error(
                'to',
                forms.ValidationError(_('An email needs to have at least one recipient.')),
            )
        return cleaned_data

    def save(self, *args, **kwargs):
        obj = super().save(*args, **kwargs)
        if self.has_changed() and 'to' in self.changed_data:
            addresses = list({address.strip().lower() for address in (obj.to or '').split(',') if address.strip()})
            found_addresses = []
            for address in addresses:
                user = User.objects.filter(email__iexact=address).first()
                if user:
                    obj.to_users.add(user)
                    found_addresses.append(address)
            addresses = set(addresses) - set(found_addresses)
            addresses = ','.join(addresses) if addresses else ''
            obj.to = addresses
            obj.save()
        return obj

    class Meta:
        model = QueuedMail
        fields = ['to', 'to_users', 'reply_to', 'cc', 'bcc', 'subject', 'text', 'scheduled_at']
        field_classes = {
            'scheduled_at': SplitDateTimeField,
        }
        widgets = {
            'to_users': EnhancedSelectMultiple,
            'scheduled_at': TalkSplitDateTimePickerWidget(),
        }
        help_texts = {
            'scheduled_at': _(
                'If set, the email will be sent at this time. Time is interpreted in the event timezone.'
            ),
        }


class WriteMailBaseForm(ScheduledAtValidationMixin, MailTemplateForm):
    empty_audience_error = _('Select at least one recipient or audience filter before sending this email.')
    empty_audience_draft_error = _('Select at least one recipient or audience filter before saving this draft.')

    skip_queue = forms.BooleanField(
        label=_('Send immediately'),
        required=False,
        help_text=_('If you check this, the emails will be sent immediately, instead of being put in the outbox.'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    scheduled_at = forms.SplitDateTimeField(
        label=_('Send later'),
        required=False,
        help_text=_('The email will be sent at this time in the event timezone.'),
        widget=TalkSplitDateTimePickerWidget(),
    )
    test_email = forms.EmailField(
        label=_('Send test email to'),
        required=False,
        help_text=_('The test email is rendered with sample data and is not counted as a sent email.'),
    )

    def __init__(self, *args, user=None, may_skip_queue=False, source_template=None, **kwargs):
        self.user = user
        self.source_template = source_template
        super().__init__(*args, **kwargs)
        if not may_skip_queue:
            self.fields.pop('skip_queue', None)

    def build_send_template(self):
        """Build an unsaved template for rendering outgoing mails without persisting it."""
        template = MailTemplate(event=self.event)
        template.subject = self.cleaned_data['subject']
        template.text = self.cleaned_data['text']
        template.reply_to = self.cleaned_data.get('reply_to') or ''
        template.bcc = self.cleaned_data.get('bcc') or ''
        return template

    def attach_template_reference(self, mail):
        mail.template = self.source_template

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data.get('scheduled_at')
        if scheduled_at is not None:
            buffer = timedelta(minutes=1)
            if scheduled_at < timezone.now() - buffer:
                raise forms.ValidationError(_('Scheduled time must be in the future.'))
        return scheduled_at

    def clean(self):
        cleaned_data = super().clean()
        skip_queue = cleaned_data.get('skip_queue')
        scheduled_at = cleaned_data.get('scheduled_at')
        if skip_queue and scheduled_at is not None:
            raise forms.ValidationError(_('You cannot select "Send immediately" and also specify a scheduled time.'))
        return cleaned_data


class WriteTeamsMailForm(WriteMailBaseForm):
    empty_audience_error = _('The selected teams have no active members with an email address.')

    recipients = forms.MultipleChoiceField(
        label=_('Recipient groups'),
        required=False,
        widget=EnhancedSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Placing reviewer emails in the outbox would lead to a **ton** of permission
        # issues: who is allowed to see them, who to edit/send them, etc.
        # Reviewer emails are always sent immediately, no scheduling — but test emails
        # and preview still use the shared Delivery controls.
        self.fields.pop('skip_queue')
        self.fields.pop('scheduled_at', None)

        reviewer_teams = self.event.teams.filter(is_reviewer=True)
        other_teams = self.event.teams.exclude(is_reviewer=True)
        if reviewer_teams and other_teams:
            self.fields['recipients'].choices = [
                (
                    _('Reviewers'),
                    [(team.pk, team.name) for team in reviewer_teams],
                ),
                (
                    _('Other teams'),
                    [(team.pk, team.name) for team in other_teams],
                ),
            ]
        else:
            self.fields['recipients'].choices = [(team.pk, team.name) for team in self.event.teams.all()]

    def get_valid_placeholders(self, **kwargs):
        return get_available_placeholders(event=self.event, kwargs=['event', 'user'])

    def get_recipients(self):
        recipients = self.cleaned_data.get('recipients')
        if recipients:
            teams = self.event.teams.all().filter(pk__in=recipients)
        else:
            teams = self.event.teams.all()
        return User.objects.filter(is_active=True, teams__in=teams, email__isnull=False).exclude(email='').distinct()

    @transaction.atomic
    def save(self):
        send_template = self.build_send_template()
        result = []
        users = self.get_recipients()
        for user in users:
            # This happens when there are template errors
            with suppress(SendMailException):
                mail = send_template.to_mail(
                    user=None,
                    event=self.event,
                    locale=user.locale,
                    context_kwargs={'user': user, 'event': self.event},
                    skip_queue=False,
                    commit=False,
                    allow_empty_address=True,
                )
                self.attach_template_reference(mail)
                mail.save()
                mail.to_users.add(user)
                mail.send(requestor=self.user)
                result.append(mail)
        return result


class WriteSessionMailForm(SubmissionFilterForm, WriteMailBaseForm):
    default_renderer = TabularFormRenderer

    submissions = forms.MultipleChoiceField(
        required=False,
        label=_('Proposals'),
        help_text=_('Select proposals that should receive the email regardless of the other filters.'),
        widget=EnhancedSelectMultiple(attrs={'placeholder': _('Proposals')}),
    )
    speakers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label=phrases.schedule.speakers if phrases.schedule else _('Speakers'),
        help_text=_('Select speakers that should receive the email regardless of the other filters.'),
        widget=EnhancedSelectMultiple(
            attrs={'placeholder': phrases.schedule.speakers if phrases.schedule else _('Speakers')}
        ),
    )

    audience_fields = (
        'state',
        'submission_type',
        'content_locale',
        'track',
        'tags',
        'answer',
        'answer__options',
        'unanswered',
        'q',
        'submissions',
        'speakers',
    )

    def __init__(self, **kwargs):
        kwargs.setdefault('show_all_filters', True)
        super().__init__(**kwargs)
        initial = kwargs.get('initial', {})
        self.filter_search = initial.get('q')
        question = initial.get('question')
        if question:
            self.filter_question = self.event.talkquestions.all().filter(pk=question).first()
            if self.filter_question:
                self.filter_option = self.filter_question.options.filter(pk=initial.get('answer__options')).first()
                self.filter_answer = initial.get('answer')
                self.filter_unanswered = initial.get('unanswered')
        self._recipients = None
        self.fields['submissions'].choices = [
            (sub.code, sub.title) for sub in self.event.submissions.all().order_by('title')
        ]
        self.fields['speakers'].queryset = self.event.submitters.all().order_by('fullname')
        composer_filter_fields = {
            'state': (_('State'), _('Proposal states')),
            'submission_type': (_('Submission type'), None),
            'track': (_('Track'), None),
            'content_locale': (_('Content locale'), None),
            'tags': (_('Tags'), None),
            'pending_state__isnull': (_('Exclude pending'), None),
        }
        for field_name, (label, help_text) in composer_filter_fields.items():
            if field_name not in self.fields:
                continue
            self.fields[field_name].label = label
            if help_text:
                self.fields[field_name].help_text = help_text
        if len(self.event.locales) > 1:
            self.fields['subject'].help_text = _(
                'If you provide only one language, that language will be used for all emails. '
                'If you provide multiple languages, the best fit for each speaker will be used.'
            )
        self.warnings = []

    def get_valid_placeholders(self, ignore_data=False):
        kwargs = ['event', 'user', 'submission', 'slot']
        if getattr(self, 'cleaned_data', None) and not ignore_data and self.cleaned_data.get('speakers'):
            kwargs.remove('submission')
            kwargs.remove('slot')
        return get_available_placeholders(event=self.event, kwargs=kwargs)

    def get_recipients(self):
        if self._recipients is None:
            self._recipients = self.build_recipients()
        return self._recipients

    def build_recipients(self):
        if not any(self.cleaned_data.get(field) for field in self.audience_fields):
            return []
        added_submissions = self.cleaned_data.get('submissions')
        added_speakers = self.cleaned_data.get('speakers')
        if (added_submissions or added_speakers) and all(
            not self.cleaned_data.get(key)
            for key in (
                'state',
                'submission_type',
                'content_locale',
                'track',
                'tags',
                'pending_state__isnull',
                'question',
            )
        ):
            # If no filters have been selected, but specific submissions or speakers,
            # we will assume the users meant to send emails to only those selected,
            # not to all proposals.
            submissions = self.event.submissions.none()
        else:
            submissions = (
                self.filter_queryset(self.event.submissions)
                .select_related('track', 'submission_type', 'event')
                .prefetch_related('speakers')
            )

        if added_submissions:
            specific_submissions = (
                self.event.submissions.filter(code__in=added_submissions)
                .select_related('track', 'submission_type', 'event')
                .prefetch_related('speakers')
            )
            submissions = submissions | specific_submissions

        result = []
        for submission in submissions:
            speakers = list(submission.speakers.all())
            current_slots = submission.current_slots or []

            # Use schedule slots if the submission is scheduled; otherwise fallback to just the speakers
            if current_slots:
                for slot in current_slots:
                    for speaker in speakers:
                        result.append(
                            {
                                'submission': submission,
                                'slot': slot,
                                'user': speaker,
                            }
                        )
            else:
                for speaker in speakers:
                    result.append(
                        {
                            'submission': submission,
                            'user': speaker,
                        }
                    )
        if added_speakers:
            for user in added_speakers:
                result.append({'user': user})
        return result

    def clean_question(self):
        return getattr(self, 'filter_question', None)

    def clean_answer__options(self):
        return getattr(self, 'filter_option', None)

    def clean_answer(self):
        return getattr(self, 'filter_answer', None)

    def clean_unanswered(self):
        return getattr(self, 'filter_unanswered', None)

    def clean_q(self):
        return getattr(self, 'filter_search', None)

    @transaction.atomic
    def save(self):
        send_template = self.build_send_template()

        mails_by_user = defaultdict(list)
        contexts = self.get_recipients()
        for context in contexts:
            with suppress(SendMailException):  # This happens when there are template errors
                locale = context['user'].locale
                if submission := context.get('submission'):
                    locale = submission.get_email_locale(context['user'].locale)
                mail = send_template.to_mail(
                    user=None,
                    event=self.event,
                    locale=locale,
                    context_kwargs=context,
                    commit=False,
                    allow_empty_address=True,
                )
                self.attach_template_reference(mail)
                mails_by_user[context['user']].append((mail, context))

        result = []
        scheduled_at = self.cleaned_data.get('scheduled_at')
        for user, user_mails in mails_by_user.items():
            # Deduplicate emails: we don't want speakers to receive the same
            # email twice, just because they have multiple submissions.
            mail_dict = defaultdict(list)
            for mail, context in user_mails:
                mail_dict[mail.subject + mail.text].append((mail, context))
            # Now we can create the emails and add the speakers to them
            for mail_list in mail_dict.values():
                mail = mail_list[0][0]
                if scheduled_at:
                    mail.scheduled_at = scheduled_at
                mail.save()
                mail.to_users.add(user)
                for __, context in mail_list:
                    if submission := context.get('submission'):
                        mail.submissions.add(submission)
                result.append(mail)
        if self.cleaned_data.get('skip_queue') and not scheduled_at:
            for mail in result:
                mail.send(requestor=self.user)
        return result


class SessionMailRecipientsForm(WriteSessionMailForm):
    """Audience preview variant of the session mail form.

    The recipient list and count are shown before the message is written, so
    subject and text are not required here. Recipient selection itself is
    inherited unchanged, which keeps the preview in step with the actual send.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for name in ('subject', 'text'):
            self.fields.pop(name, None)


class QueuedMailFilterForm(forms.Form):
    track = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Track.objects.none(),
        widget=SelectMultipleWithCount(attrs={'title': _('Tracks')}, color_field='color'),
    )

    default_renderer = InlineFormRenderer

    def __init__(self, *args, event=None, sent=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

        # Only show track filter if tracks are enabled
        if not event.get_feature_flag('use_tracks'):
            self.fields.pop('track')
        else:
            mail_filter = Q(submissions__mails__event=event)
            if sent is not None:
                mail_filter &= Q(submissions__mails__sent__isnull=not sent)

            self.fields['track'].queryset = event.tracks.annotate(
                count=Count(
                    'submissions__mails',
                    distinct=True,
                    filter=mail_filter,
                )
            ).order_by('-count')

    def filter_queryset(self, qs):
        tracks = self.cleaned_data.get('track')
        if tracks:
            qs = qs.filter(submissions__track__in=tracks)
        return qs.distinct()
