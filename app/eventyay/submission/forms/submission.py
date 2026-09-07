from django import forms
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField

from eventyay.base.models import (
    Answer,
    Question,
    Submission,
    SubmissionStates,
    Tag,
    TalkQuestionTarget,
    Track,
)
from eventyay.base.models.cfp import default_fields
from eventyay.base.models.resource import get_slide_resources
from eventyay.cfp.forms.cfp import CfPFormMixin
from eventyay.common.forms.fields import ImageField
from eventyay.common.forms.mixins import ConfiguredFieldOrderMixin, PublicContent, QuestionFieldsMixin, RequestRequire
from eventyay.common.forms.renderers import InlineFormRenderer
from eventyay.common.forms.widgets import (
    EnhancedSelect,
    RichTextWidget,
    SearchInput,
    SelectMultipleWithCount,
)
from eventyay.common.text.phrases import phrases
from eventyay.common.utils.language import localize_event_text
from eventyay.common.views.mixins import Filterable
from eventyay.submission.constants import AUTO_DRAFT_TITLE
from eventyay.submission.forms.resource import (
    SlidesField,
    SlidesData,
    get_slides_max_count,
    save_slides_resource,
)


class EventLocalizedSafeModelChoiceField(SafeModelChoiceField):
    def label_from_instance(self, obj):
        return localize_event_text(getattr(obj, 'name', obj))


class InfoForm(
    CfPFormMixin, ConfiguredFieldOrderMixin, QuestionFieldsMixin, RequestRequire, PublicContent, forms.ModelForm
):
    image = ImageField(
        required=False,
        label=_('Session image'),
        help_text=_('Use this if you want an illustration to go with your proposal.'),
    )
    slides = SlidesField(required=False, label=_('Slides'))
    content_locale = forms.ChoiceField(label=phrases.base.language)

    def __init__(self, event, **kwargs):
        self.event = event
        self.readonly = kwargs.pop('readonly', False)
        self.access_code = kwargs.pop('access_code', None)
        self.default_values = {}
        instance = kwargs.get('instance')
        self.original_instance_title = getattr(instance, 'title', None)
        initial = kwargs.pop('initial', {}) or {}
        if initial.get('title') == AUTO_DRAFT_TITLE or getattr(instance, 'title', None) == AUTO_DRAFT_TITLE:
            initial['title'] = ''
        if not instance or not instance.submission_type:
            initial['submission_type'] = (
                getattr(self.access_code, 'submission_type', None)
                or initial.get('submission_type')
                or (self.event.cfp.default_type if hasattr(self.event, 'cfp') else None)
                or ''
            )
        if not instance and self.access_code:
            initial['track'] = self.access_code.track
        if not instance or not instance.content_locale:
            initial['content_locale'] = self.event.locale

        super().__init__(initial=initial, **kwargs)
        self.submission = self.instance

        if 'abstract' in self.fields:
            self.fields['abstract'].widget.attrs['rows'] = 2

        self._set_track(instance=instance)
        self._set_submission_types(instance=instance)
        self._set_locales()
        self._set_slot_count(instance=instance)
        if 'slides' in self.fields:
            slides_resources = list(get_slide_resources(instance)) if instance and instance.pk else []
            self.initial['slides'] = slides_resources
            self.fields['slides'].existing_resources = slides_resources
            self.fields['slides'].set_max_items(get_slides_max_count(self.event))

        self.inject_questions_into_fields(
            target=TalkQuestionTarget.SUBMISSION,
            event=self.event,
            submission=instance,
            track=initial.get('track'),
            submission_type=initial.get('submission_type'),
            readonly=self.readonly,
        )

        self.order_fields_by_config('session')

        if self.readonly:
            for field in self.fields.values():
                field.disabled = True

    def _set_track(self, instance=None):
        if 'track' in self.fields:
            if (
                not self.event.get_feature_flag('use_tracks')
                or instance
                and instance.state != SubmissionStates.SUBMITTED
            ):
                self.fields.pop('track')
                return

            access_code = self.access_code or getattr(instance, 'access_code', None)
            if not access_code or not access_code.track:
                track_filter = self.event.tracks.filter(requires_access_code=False)
                # ensure current track selection can be preserved
                if instance and instance.track and instance.track.requires_access_code:
                    track_filter = self.event.tracks.filter(Q(requires_access_code=False) | Q(pk=instance.track.pk))

                self.fields['track'].queryset = track_filter
            else:
                self.fields['track'].queryset = self.event.tracks.filter(pk=access_code.track.pk)
            if len(self.fields['track'].queryset) == 1 and self.fields['track'].required:
                self.default_values['track'] = self.fields['track'].queryset.first()
                self.fields.pop('track')

    def _set_submission_types(self, instance=None):
        _now = now()
        submission_types = self.event.submission_types
        if instance and instance.pk and (
            instance.state != SubmissionStates.SUBMITTED
            or not (hasattr(self.event, 'cfp') and self.event.cfp.is_open)
        ):
            self.fields['submission_type'].queryset = submission_types.filter(pk=instance.submission_type_id)
            self.fields['submission_type'].disabled = True
            return
        access_code = self.access_code or getattr(instance, 'access_code', None)
        if access_code and not access_code.submission_type:
            pks = set(submission_types.values_list('pk', flat=True))
        elif access_code:
            pks = {access_code.submission_type.pk}
        else:
            queryset = submission_types.filter(requires_access_code=False)
            _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
            if not _cfp or not _cfp.deadline or _cfp.deadline >= _now:
                # No global deadline or still open
                types = queryset.exclude(deadline__lt=_now)
            else:
                types = queryset.filter(deadline__gte=_now)
            pks = set(types.values_list('pk', flat=True))
        if instance and instance.pk:
            pks |= {instance.submission_type.pk}
        if len(pks) == 1:
            single_type = submission_types.get(pk=list(pks)[0])
            self.default_values['submission_type'] = single_type
            # Keep the field visible but disabled — speakers can see which session
            # type they are submitting for even when there is only one available.
            self.fields['submission_type'].queryset = submission_types.filter(pk=single_type.pk)
            self.fields['submission_type'].required = True
            self.fields['submission_type'].empty_label = None
            self.fields['submission_type'].disabled = True
            # Ensure the initial value is set so Django's disabled-field logic picks it up.
            self.initial['submission_type'] = single_type
        else:
            self.fields['submission_type'].queryset = submission_types.filter(pk__in=pks)
            self.fields['submission_type'].required = True
            if hasattr(self.event, 'cfp') and self.event.cfp.default_type:
                self.fields['submission_type'].empty_label = None
            else:
                self.fields['submission_type'].empty_label = _('Select a session type')
            if 'duration' in self.fields and not self.fields['duration'].required:
                self.fields['duration'].help_text += ' ' + str(
                    _('Leave empty to use the default duration for the session type.')
                )

    def _set_locales(self):
        if 'content_locale' in self.fields:
            _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
            saved_visibility = (_cfp.fields.get('content_locale', default_fields()['content_locale']).get('visibility') if _cfp else 'do_not_ask')
            if len(self.event.content_locales) <= 1 or saved_visibility == 'do_not_ask':
                default_locale = self.event.content_locales[0] if self.event.content_locales else self.event.locale
                self.default_values['content_locale'] = default_locale
                self.fields.pop('content_locale')
            else:
                choices = list(self.event.named_content_locales)
                if self.instance and self.instance.pk and self.instance.content_locale:
                    choice_codes = {c[0] for c in choices}
                    if self.instance.content_locale not in choice_codes:
                        choices.append((self.instance.content_locale, self.instance.get_content_locale_display()))
                self.fields['content_locale'].choices = choices

    def _set_slot_count(self, instance=None):
        if not self.event.get_feature_flag('present_multiple_times'):
            self.fields.pop('slot_count', None)
        elif 'slot_count' in self.fields and instance and instance.state in SubmissionStates.accepted_states:
            self.fields['slot_count'].disabled = True
            self.fields['slot_count'].help_text += ' ' + str(
                _('Please contact the organizers if you want to change how often you’re presenting this proposal.')
            )

    def save(self, *args, **kwargs):
        for key, value in self.default_values.items():
            setattr(self.instance, key, value)
        self.errors
        self._preserve_auto_draft_title()
        result = super().save(*args, **kwargs)
        if 'image' in self.cleaned_data:
            self.instance.process_image('image')
        if 'slides' in self.cleaned_data:
            save_slides_resource(self.instance, self.cleaned_data['slides'])
        for key, value in self.cleaned_data.items():
            if key.startswith('question_'):
                self.save_questions(key, value)
        return result

    def clean(self):
        cleaned_data = super().clean()

        if self.not_strict and not self.draft_save:
            self._validate_required_step_fields(cleaned_data)
            return cleaned_data

        if not (self.draft_save or self.not_strict):
            return cleaned_data

        draft_field_names = [name for name in self.fields if self._is_draft_content_field_name(name)]
        has_real_user_data = any(
            self._counts_as_draft_content(key, value)
            for key, value in cleaned_data.items()
            if key in draft_field_names
        )
        if not has_real_user_data:
            raise forms.ValidationError(self._get_empty_content_error_message())
        return cleaned_data

    def _validate_required_step_fields(self, cleaned_data):
        _cfp_fields = (
            self.event.cfp.fields if hasattr(self.event, 'cfp') else default_fields()
        )
        for key in self.Meta.request_require:
            visibility = _cfp_fields.get(key, default_fields()[key])['visibility']
            if visibility != 'required':
                continue
            if key in self.default_values or key not in self.fields:
                continue
            value = cleaned_data.get(key)
            if not self._has_real_draft_value(key, value):
                self.add_error(key, forms.ValidationError(_('This field is required.'), code='required_step_field'))

        question_cache = {
            field.question.pk: field.question
            for field_name, field in self.fields.items()
            if field_name.startswith('question_') and hasattr(field, 'question')
        }

        def question_is_visible(parent_id, dep_values):
            if parent_id not in question_cache:
                return False
            parent_question = question_cache[parent_id]
            if parent_question.dependency_question_id and not question_is_visible(
                parent_question.dependency_question_id,
                parent_question.dependency_values,
            ):
                return False
            parent_field_name = f'question_{parent_id}'
            if parent_field_name not in cleaned_data:
                return False
            parent_value = cleaned_data[parent_field_name]
            if parent_value is None or parent_value == '':
                return False
            if isinstance(parent_value, bool):
                return ('True' in dep_values and parent_value) or ('False' in dep_values and not parent_value)
            if isinstance(parent_value, str):
                return parent_value in dep_values
            if hasattr(parent_value, '__iter__'):
                return any(
                    (str(v.pk) if hasattr(v, 'pk') else str(v)) in dep_values
                    for v in parent_value
                )
            if hasattr(parent_value, 'pk'):
                return str(parent_value.pk) in dep_values
            return str(parent_value) in dep_values

        for field_name, field in self.fields.items():
            if not field_name.startswith('question_') or not hasattr(field, 'question'):
                continue
            question = field.question
            if not question.required:
                continue
            if question.dependency_question_id and not question_is_visible(
                question.dependency_question_id,
                question.dependency_values,
            ):
                continue
            value = cleaned_data.get(field_name)
            if not self._has_real_draft_value(field_name, value):
                self.add_error(field_name, forms.ValidationError(_('This field is required.'), code='required_step_field'))

    def _get_empty_content_error_message(self):
        return _('Please fill at least one field.')

    def _preserve_auto_draft_title(self):
        if not hasattr(self, 'cleaned_data'):
            return
        cleaned_title = (self.cleaned_data.get('title') or '').strip()
        if self.draft_save and not cleaned_title:
            self.cleaned_data['title'] = AUTO_DRAFT_TITLE
            self.instance.title = AUTO_DRAFT_TITLE

    @staticmethod
    def _is_draft_content_field_name(name):
        return name not in {'submission_type', 'content_locale'}

    def _counts_as_draft_content(self, key, value):
        if key.startswith('question_'):
            field = self.fields.get(key)
            if not self._question_field_has_user_content(field, value):
                return False
        return self._has_real_draft_value(key, value)

    def _question_field_has_user_content(self, field, value):
        if not self._has_real_draft_value(getattr(field, 'question', None), value):
            return False
        if getattr(field, 'answer', None):
            return True
        return self._normalize_draft_value(value) != self._normalize_draft_value(getattr(field, 'initial', None))

    @staticmethod
    def _has_real_draft_value(key, value):
        if key == 'title' and value == AUTO_DRAFT_TITLE:
            return False
        if key == 'slot_count' and value == 1:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, SlidesData):
            return value.has_value
        if isinstance(value, bool):
            return value
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        if hasattr(value, '__len__'):
            return len(value) > 0
        return value is not None

    @classmethod
    def _normalize_draft_value(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, bool):
            return value
        if isinstance(value, SlidesData):
            return value.serialize()
        if hasattr(value, 'pk'):
            return value.pk
        if hasattr(value, 'code'):
            return value.code
        if isinstance(value, dict):
            return {key: cls._normalize_draft_value(val) for key, val in value.items()}
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            return [cls._normalize_draft_value(element) for element in value]
        return value

    @cached_property
    def submission_fields(self):
        return [
            self[name]
            for name, field in self.fields.items()
            if getattr(field, 'question', None) and field.question.target == TalkQuestionTarget.SUBMISSION
        ]

    @cached_property
    def speaker_fields(self):
        return [
            self[name]
            for name, field in self.fields.items()
            if getattr(field, 'question', None) and field.question.target == TalkQuestionTarget.SPEAKER
        ]

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'track',
            'content_locale',
            'abstract',
            'description',
            'notes',
            'slot_count',
            'do_not_record',
            'image',
            'slides',
            'duration',
        ]
        request_require = [
            'title',
            'abstract',
            'description',
            'notes',
            'slot_count',
            'image',
            'slides',
            'do_not_record',
            'track',
            'duration',
            'content_locale',
        ]
        public_fields = ['title', 'abstract', 'description', 'image', 'slides']
        widgets = {
            'abstract': RichTextWidget,
            'description': RichTextWidget,
            'notes': RichTextWidget,
            'track': EnhancedSelect(description_field='description', color_field='color'),
        }
        field_classes = {
            'submission_type': EventLocalizedSafeModelChoiceField,
            'track': EventLocalizedSafeModelChoiceField,
        }


class CountableOption:
    def __init__(self, name, count):
        self.name = name
        self.count = count

    def __str__(self):
        return str(self.name)


class SubmissionFilterForm(forms.Form):
    state = forms.MultipleChoiceField(
        required=False,
        choices=[
            (state, name)
            for (state, name) in SubmissionStates.get_choices()
            if state not in (SubmissionStates.DELETED, SubmissionStates.DRAFT)
        ],
        widget=SelectMultipleWithCount(
            attrs={'title': _('Proposal states')},
            color_field=SubmissionStates.get_color,
        ),
    )
    submission_type = forms.MultipleChoiceField(
        required=False,
        widget=SelectMultipleWithCount(attrs={'title': _('Session types')}),
    )
    pending_state__isnull = forms.BooleanField(
        required=False,
        label=_('exclude pending'),
    )
    content_locale = forms.MultipleChoiceField(
        required=False,
        widget=SelectMultipleWithCount(attrs={'title': phrases.base.language}),
    )
    track = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Track.objects.none(),
        widget=SelectMultipleWithCount(attrs={'title': _('Tracks')}, color_field='color'),
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
        widget=SelectMultipleWithCount(attrs={'title': _('Tags')}, color_field='color'),
    )
    question = SafeModelChoiceField(queryset=Question.objects.none(), required=False)
    unanswered = forms.BooleanField(required=False)
    answer = forms.CharField(required=False)
    answer__options = forms.IntegerField(required=False)
    q = forms.CharField(required=False, label=_('Search'), widget=SearchInput)

    default_renderer = InlineFormRenderer

    def __init__(self, event, *args, limit_tracks=False, search_fields=None, show_all_filters=False, **kwargs):
        self.event = event
        self.search_fields = search_fields or (
            'code__icontains',
            'title__icontains',
            'speakers__fullname__icontains',
        )
        usable_states = kwargs.pop('usable_states', None)
        initial = kwargs.pop('initial', {}) or {}
        initial['exclude_pending'] = False
        super().__init__(*args, initial=initial, **kwargs)
        qs = event.submissions
        state_qs = Submission.objects.filter(event=event)
        if usable_states:
            qs = qs.filter(state__in=usable_states)
            state_qs = state_qs.filter(state__in=usable_states)
        state_count = {
            d['state']: d['state__count'] for d in state_qs.order_by('state').values('state').annotate(Count('state'))
        }
        state_count.update(
            {
                f'pending_state__{d["pending_state"]}': d['pending_state__count']
                for d in state_qs.filter(pending_state__isnull=False)
                .order_by('pending_state')
                .values('pending_state')
                .annotate(Count('pending_state'))
            }
        )
        sub_types = event.submission_types.all()
        if limit_tracks and isinstance(limit_tracks, (list, tuple, set)):
            limit_tracks = event.tracks.filter(pk__in=[track.pk for track in limit_tracks])
        tracks = limit_tracks or event.tracks.all()
        languages = event.named_content_locales
        if len(sub_types) > 1 or show_all_filters:
            type_count = {
                d['submission_type_id']: d['submission_type_id__count']
                for d in qs.order_by('submission_type_id')
                .values('submission_type_id')
                .annotate(Count('submission_type_id'))
            }
            self.fields['submission_type'].choices = [
                (
                    sub_type.pk,
                    CountableOption(sub_type.name, type_count.get(sub_type.pk, 0)),
                )
                for sub_type in sub_types
            ]
        else:
            self.fields.pop('submission_type', None)
        if len(tracks) > 1 or show_all_filters:
            self.fields['track'].queryset = tracks.annotate(
                count=Count(
                    'submissions',
                    distinct=True,
                    filter=Q(event=event)
                    & ~Q(
                        submissions__state__in=[
                            SubmissionStates.DELETED,
                            SubmissionStates.DRAFT,
                        ]
                    ),
                )
            ).order_by('-count')
        else:
            self.fields.pop('track', None)
        if len(languages) > 1 or show_all_filters:
            language_count = {
                d['content_locale']: d['content_locale__count']
                for d in qs.order_by('content_locale').values('content_locale').annotate(Count('content_locale'))
            }
            self.fields['content_locale'].choices = [
                (code, CountableOption(name, language_count.get(code, 0))) for code, name in languages
            ]
        else:
            self.fields.pop('content_locale', None)

        if self.event.tags.all().exists() or show_all_filters:
            self.fields['tags'].queryset = event.tags.prefetch_related('submissions').annotate(
                submission_count=Count('submissions', distinct=True)
            )
        else:
            self.fields.pop('tags', None)

        if usable_states:
            usable_states = [choice for choice in self.fields['state'].choices if choice[0] in usable_states]
        else:
            usable_states = self.fields['state'].choices
        usable_states += [
            (
                f'pending_state__{choice[0]}',
                str(_('Pending {state}')).format(state=choice[1]),
            )
            for choice in usable_states
        ]
        self.fields['state'].choices = [
            (
                choice[0],
                CountableOption(choice[1].capitalize(), state_count.get(choice[0], 0)),
            )
            for choice in usable_states
        ]
        self.fields['question'].queryset = event.talkquestions.all()

    def _filter_question(self, qs, question=None, answer=None, option=None, unanswered=False):
        if question and (answer or option):
            if option:
                option = option.pk if hasattr(option, 'pk') else option
                answers = Answer.objects.filter(
                    submission_id=OuterRef('pk'),
                    question_id=question,
                    options__pk=option,
                )
            else:
                answers = Answer.objects.filter(
                    submission_id=OuterRef('pk'),
                    question_id=question,
                    answer__exact=answer,
                )
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=True)
        elif question and unanswered:
            answers = Answer.objects.filter(question_id=question, submission_id=OuterRef('pk'))
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=False)
        return qs

    def filter_queryset(self, qs):
        for field in ('submission_type', 'content_locale', 'track', 'tags'):
            value = self.cleaned_data.get(field)
            if value:
                qs = qs.filter(**{f'{field}__in': value})

        state_filter = self.cleaned_data.get('state')
        if state_filter:
            states = [state for state in state_filter if not state.startswith('pending_state__')]
            pending_states = [state.split('__')[1] for state in state_filter if state not in states]
            if states and not pending_states:
                qs = qs.filter(state__in=states)
            elif pending_states and not states:
                qs = qs.filter(pending_state__in=pending_states)
            else:
                qs = qs.filter(Q(state__in=states) | Q(pending_state__in=pending_states))

        if self.cleaned_data.get('pending_state__isnull'):
            qs = qs.filter(pending_state__isnull=True)

        search = self.cleaned_data.get('q')
        if search:
            qs = Filterable.handle_search(qs, search, self.search_fields)

        qs = self._filter_question(
            qs,
            question=self.cleaned_data.get('question'),
            answer=self.cleaned_data.get('answer'),
            option=self.cleaned_data.get('answer__options'),
            unanswered=self.cleaned_data.get('unanswered'),
        )
        if not self.cleaned_data.get('state'):
            qs = qs.exclude(state='deleted')
        return qs
