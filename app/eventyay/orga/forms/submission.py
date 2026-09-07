import json

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField

from eventyay.base.models import Submission, SubmissionStates, TalkSlot, User
from eventyay.base.models.cfp import default_fields
from eventyay.base.models.resource import get_slide_resources
from eventyay.base.models.room import rooms_for_talk_assignment
from eventyay.base.services.etherpad import validate_etherpad_url
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.forms.fields import ImageField
from eventyay.common.forms.mixins import ReadOnlyFlag, RequestRequire
from eventyay.common.forms.renderers import InlineFormLabelRenderer, InlineFormRenderer
from eventyay.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    HtmlDateTimeInput,
    RichTextWidget,
    TextInputWithAddon,
)
from eventyay.common.text.phrases import phrases
from eventyay.submission.forms.resource import (
    SlidesField,
    get_slides_max_count,
    save_slides_resource,
)


class SubmissionForm(ReadOnlyFlag, RequestRequire, forms.ModelForm):
    content_locale = forms.ChoiceField(label=phrases.base.language)
    slides = SlidesField(required=False, label=_('Slides'))

    def __init__(self, event, anonymise=False, **kwargs):
        self.event = event
        initial_slot = {}
        instance = kwargs.get('instance')
        if instance and instance.pk:
            slot = (
                instance.slots.filter(schedule__version__isnull=True)
                .select_related('room')
                .filter(start__isnull=False)
                .order_by('start')
                .first()
            )
            if slot:
                initial_slot = {
                    'room': slot.room,
                    'start': (slot.local_start.strftime('%Y-%m-%dT%H:%M') if slot.local_start else ''),
                    'end': (slot.local_end.strftime('%Y-%m-%dT%H:%M') if slot.real_end else ''),
                }
        if anonymise:
            kwargs.pop('initial', None)
            initial = {}
            instance = kwargs.pop('instance', None)
            previous_data = instance.anonymised
            for key in self._meta.fields:
                initial[key] = previous_data.get(key) or getattr(instance, key, None) or ''
                if hasattr(initial[key], 'all'):  # Tags, for the moment
                    initial[key] = initial[key].all()
            kwargs['initial'] = initial
        kwargs['initial'] = kwargs.get('initial') or {}
        kwargs['initial'].update(initial_slot)
        super().__init__(**kwargs)
        if 'submission_type' in self.fields:
            self.fields['submission_type'].queryset = self.event.submission_types.all()
        if not self.event.tags.all().exists():
            self.fields.pop('tags', None)
        elif 'tags' in self.fields:
            self.fields['tags'].queryset = self.event.tags.all()
            self.fields['tags'].required = False

        self.is_creating = False
        if not self.instance.pk:
            self.is_creating = True
            if not anonymise:
                self.fields['state'] = forms.ChoiceField(
                    label=_('Proposal state'),
                    choices=[
                        (choice, name)
                        for (choice, name) in SubmissionStates.get_choices()
                        if choice != SubmissionStates.DELETED and choice != SubmissionStates.DRAFT
                    ],
                    initial=SubmissionStates.SUBMITTED,
                    required=True,
                    widget=EnhancedSelect(color_field=SubmissionStates.get_color),
                )
        if not self.instance.pk or self.instance.state in SubmissionStates.accepted_states:
            self.fields['room'] = forms.ModelChoiceField(
                required=False,
                queryset=rooms_for_talk_assignment(event, has_submission=True),
                label=TalkSlot._meta.get_field('room').verbose_name,
                initial=initial_slot.get('room'),
                widget=EnhancedSelect,
            )
            self.fields['start'] = forms.DateTimeField(
                required=False,
                label=TalkSlot._meta.get_field('start').verbose_name,
                widget=HtmlDateTimeInput,
                initial=initial_slot.get('start'),
            )
            self.fields['end'] = forms.DateTimeField(
                required=False,
                label=TalkSlot._meta.get_field('end').verbose_name,
                widget=HtmlDateTimeInput,
                initial=initial_slot.get('end'),
            )
        if 'abstract' in self.fields:
            self.fields['abstract'].widget.attrs['rows'] = 2
        if 'slides' in self.fields:
            slides_resources = list(get_slide_resources(instance)) if instance and instance.pk else []
            self.initial['slides'] = slides_resources
            self.fields['slides'].existing_resources = slides_resources
            self.fields['slides'].set_max_items(get_slides_max_count(self.event))
        if not event.get_feature_flag('present_multiple_times'):
            self.fields.pop('slot_count', None)
        if not event.get_feature_flag('use_tracks'):
            self.fields.pop('track', None)
        elif 'track' in self.fields:
            self.fields['track'].queryset = event.tracks.all()
        if 'content_locale' in self.fields:
            _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
            saved_visibility = (_cfp.fields.get('content_locale', default_fields()['content_locale']).get('visibility') if _cfp else 'do_not_ask')
            if len(self.event.content_locales) <= 1 or saved_visibility == 'do_not_ask':
                self.fields.pop('content_locale')
            else:
                choices = list(self.event.named_content_locales)
                if self.instance and self.instance.pk and self.instance.content_locale:
                    choice_codes = {c[0] for c in choices}
                    if self.instance.content_locale not in choice_codes:
                        choices.append((self.instance.content_locale, self.instance.get_content_locale_display()))
                self.fields['content_locale'].choices = choices
        # If duration is not required, point out that the default is the session type's duration,
        # but only if there is more than one session type, because otherwise users will be
        # confused what that is.
        if (
            'duration' in self.fields
            and not self.fields['duration'].required
            and 'submission_type' in self.fields
            and len(self.fields['submission_type'].queryset) > 1
        ):
            self.fields['duration'].help_text += ' ' + str(
                _('Leave empty to use the default duration for the session type.')
            )
        # Show the field only when both the platform and the event enable Etherpad.
        gs = GlobalSettingsObject().settings
        platform_ready = bool(gs.etherpad_enabled and gs.etherpad_base_url)
        if not (platform_ready and event.get_feature_flag('etherpad_enabled')):
            self.fields.pop('etherpad_url', None)

    def clean_etherpad_url(self):
        url = self.cleaned_data.get('etherpad_url')
        if url:
            try:
                validate_etherpad_url(url)
            except DjangoValidationError as exc:
                raise forms.ValidationError(_('Please enter a valid Etherpad URL.')) from exc
        return url

    def clean(self):
        data = super().clean()
        start = data.get('start')
        end = data.get('end')
        if start and end and start > end:
            self.add_error(
                'end',
                forms.ValidationError(
                    _('The end time has to be after the start time.'),
                ),
            )
        return data

    def save(self, *args, **kwargs):
        if 'content_locale' not in self.fields:
            self.instance.content_locale = self.event.content_locales[0] if self.event.content_locales else self.event.locale
        instance = super().save(*args, **kwargs)
        if self.is_creating:
            instance._set_state(self.cleaned_data['state'], force=True)
        else:
            if 'duration' in self.changed_data:
                instance.update_duration()
            if 'track' in self.changed_data:
                instance.update_review_scores()
            if 'slot_count' in self.changed_data and 'slot_count' in self.initial:
                instance.update_talk_slots()
        if (
            instance.state in SubmissionStates.accepted_states
            and self.cleaned_data.get('room')
            and self.cleaned_data.get('start')
            and any(field in self.changed_data for field in ('room', 'start', 'end'))
        ):
            slot = instance.slots.filter(schedule=instance.event.wip_schedule).order_by('start').first()
            slot.room = self.cleaned_data.get('room')
            slot.start = self.cleaned_data.get('start')
            slot.end = self.cleaned_data.get('end')
            slot.save()
        if 'slides' in self.cleaned_data:
            save_slides_resource(instance, self.cleaned_data['slides'])
        return instance

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'track',
            'tags',
            'abstract',
            'description',
            'notes',
            'internal_notes',
            'content_locale',
            'do_not_record',
            'duration',
            'slot_count',
            'image',
            'slides',
            'is_featured',
            'etherpad_url',
        ]
        widgets = {
            'tags': EnhancedSelectMultiple(color_field='color'),
            'track': EnhancedSelect(color_field='color'),
            'submission_type': EnhancedSelect,
            'abstract': RichTextWidget,
            'description': RichTextWidget,
            'notes': RichTextWidget,
            'duration': TextInputWithAddon(addon_after=_('minutes')),
        }
        field_classes = {
            'submission_type': SafeModelChoiceField,
            'tags': SafeModelMultipleChoiceField,
            'track': SafeModelChoiceField,
            'image': ImageField,
        }
        request_require = {
            'title',
            'abstract',
            'description',
            'notes',
            'slot_count',
            'image',
            'slides',
            'do_not_record',
            'content_locale',
        }


class AnonymiseForm(SubmissionForm):
    default_renderer = InlineFormRenderer

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if not instance or not instance.pk:
            raise Exception('Cannot anonymise unsaved submission.')
        kwargs['event'] = instance.event
        kwargs['anonymise'] = True
        super().__init__(*args, **kwargs)
        self._instance = instance
        to_be_removed = ['content_locale']
        for key, field in self.fields.items():
            try:
                field.plaintext = getattr(self._instance, key)
                field.required = False
            except AttributeError:
                to_be_removed.append(key)
        for key in to_be_removed:
            self.fields.pop(key, None)

    def save(self):
        anonymised_data = {'_anonymised': True}
        for key, value in self.cleaned_data.items():
            if value != getattr(self._instance, key, ''):
                anonymised_data[key] = value
        self._instance.anonymised_data = json.dumps(anonymised_data)
        self._instance.save(update_fields=['anonymised_data'])

    class Meta:
        model = Submission
        fields = [
            'title',
            'abstract',
            'description',
            'notes',
        ]
        request_require = fields


class SubmissionStateChangeForm(forms.Form):
    pending = forms.BooleanField(
        label=_('Mark the new state as “pending”'),
        help_text=_(
            'If you mark state changes as pending, they won’t be visible to speakers right away. '
            'You can always apply pending changes for some or all proposals in one go once '
            'you’re ready to make your decisions public.'
        ),
        required=False,
        initial=False,
    )


def get_speaker_choice_label(*, name: str | None, email: str) -> str:
    return f'{name} ({email})' if name else email


class AddSpeakerForm(forms.Form):
    email = forms.EmailField(
        label=phrases.cfp.speaker_email,
        help_text=_('The email address of the speaker holding the session. They will be invited to create an account.'),
        required=False,
        widget=forms.Select,
    )
    name = forms.CharField(
        label=_('Speaker name'),
        help_text=_('The name of the speaker that should be displayed publicly.'),
        required=False,
    )
    biography = forms.CharField(
        label=_('Biography'),
        required=False,
        widget=RichTextWidget(),
    )
    locale = forms.ChoiceField(
        label=_('Invite language'),
        choices=[],
        required=False,
        help_text=_('The language in which the speaker will receive their invitation email.'),
        widget=EnhancedSelect,
    )

    def __init__(
        self,
        *args,
        event=None,
        form_renderer=None,
        require_name=False,
        include_biography=False,
        draft_save=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.event = event
        self.require_name = require_name
        self.draft_save = draft_save

        self.biography_required = False
        if not include_biography:
            self.fields.pop('biography', None)
        else:
            cfp_fields = event.cfp.fields if hasattr(event, 'cfp') else default_fields()
            visibility = cfp_fields.get('biography', default_fields()['biography'])['visibility']
            if visibility == 'do_not_ask':
                self.fields.pop('biography', None)
            else:
                # Keep optional unless a speaker is actually added; validate in clean().
                self.biography_required = visibility == 'required'
                self.fields['biography'].required = False
        email_key = self.add_prefix('email')
        name_key = self.add_prefix('name')
        email_widget = self.fields['email'].widget
        if isinstance(email_widget, forms.Select) and self.is_bound and (email := self.data.get(email_key)):
            name = self.data.get(name_key)
            email_widget.choices = [(email, get_speaker_choice_label(name=name, email=email))]
        if require_name:
            self.fields['email'].required = True
            self.fields['name'].required = True
            if self.is_bound and self.data.get(email_key) and not self.data.get(name_key):
                existing_user = User.objects.filter(email__iexact=self.data[email_key]).only('fullname').first()
                if existing_user and existing_user.fullname:
                    self.data = self.data.copy()
                    self.data[name_key] = existing_user.fullname
        if not event.named_locales or len(event.named_locales) < 2:
            self.fields.pop('locale')
        else:
            self.fields['locale'].choices = event.named_locales
            self.fields['locale'].initial = event.locale

    def clean(self):
        data = super().clean()
        if data.get('name') and not data.get('email'):
            self.add_error('email', _('Please provide an email address.'))

        existing_biography = False
        email = data.get('email')
        if email:
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                existing_profile = existing_user.profiles.filter(event=self.event).first()
                existing_biography = bool(existing_profile and existing_profile.biography)

        if (
            not self.draft_save
            and email
            and getattr(self, 'biography_required', False)
            and not existing_biography
            and not data.get('biography')
        ):
            self.add_error('biography', _('This field is required.'))
        return data
class AddSpeakerInlineForm(AddSpeakerForm):
    default_renderer = InlineFormLabelRenderer
