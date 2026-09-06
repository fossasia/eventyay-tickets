from functools import partial

from django import forms
from django.forms import Textarea
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField
from i18nfield.forms import I18nModelForm

from eventyay.base.models import Event, SpeakerProfile, TalkQuestion, TalkQuestionTarget, User
from eventyay.base.models.cfp import default_fields
from eventyay.base.models.information import SpeakerInformation
from eventyay.base.models.submission import SubmissionStates
from eventyay.cfp.forms.cfp import CfPFormMixin
from eventyay.common.templatetags.filesize import filesize
from eventyay.common.forms.fields import (
    ImageField,
    NewPasswordConfirmationField,
    NewPasswordField,
    SizeFileField,
)
from eventyay.common.forms.mixins import (
    ConfiguredFieldOrderMixin,
    I18nHelpText,
    PublicContent,
    QuestionFieldsMixin,
    ReadOnlyFlag,
    RequestRequire,
)
from eventyay.common.forms.renderers import InlineFormLabelRenderer, InlineFormRenderer
from eventyay.common.forms.widgets import (
    ClearableBasenameFileInput,
    EnhancedSelect,
    EnhancedSelectMultiple,
    RichTextWidget,
)
from eventyay.common.text.phrases import phrases
from eventyay.consts import SizeKey
from eventyay.schedule.forms import AvailabilitiesFormMixin


AVATAR_LICENSE_TEXT_WORD_LIMIT = 3000
AVATAR_LICENSE_TEXT_VALIDATION_ERROR = _(
    'Please keep this field below %(word_limit)s words. Do not paste image files or encoded image data here.'
) % {'word_limit': AVATAR_LICENSE_TEXT_WORD_LIMIT}


def get_email_address_error():
    return (
        _('There already exists an account for this email address.')
        + ' '
        + _('Please choose a different email address.')
    )


def validate_avatar_license_text(value):
    if not value:
        return value
    if value.lstrip().startswith('data:image/'):
        raise ValidationError(AVATAR_LICENSE_TEXT_VALIDATION_ERROR)
    words = value.split(maxsplit=AVATAR_LICENSE_TEXT_WORD_LIMIT + 1)
    if len(words) > AVATAR_LICENSE_TEXT_WORD_LIMIT:
        raise ValidationError(AVATAR_LICENSE_TEXT_VALIDATION_ERROR)
    return value


class SpeakerProfileForm(
    CfPFormMixin,
    ConfiguredFieldOrderMixin,
    QuestionFieldsMixin,
    AvailabilitiesFormMixin,
    ReadOnlyFlag,
    PublicContent,
    RequestRequire,
    forms.ModelForm,
):
    additional_speaker = forms.EmailField(
        label=_('Additional Speaker'),
        help_text=_(
            'If you have a co-speaker, please add their email address here, and we will invite them '
            'to create an account. If you have more than one co-speaker, you can add more speakers '
            'after finishing the proposal process.'
        ),
        required=False,
    )
    USER_FIELDS = [
        'fullname',
        'email',
        'avatar',
        'avatar_source',
        'avatar_license',
        'get_gravatar',
    ]
    FIRST_TIME_EXCLUDE = ['email']

    def __init__(self, *args, name=None, enforce_account_name_match=False, **kwargs):
        self.add_additional_speaker = kwargs.pop('add_additional_speaker', False)
        self.user = kwargs.pop('user', None)
        self.event = kwargs.pop('event', None)
        self.with_email = kwargs.pop('with_email', True)
        self.essential_only = kwargs.pop('essential_only', False)
        self.enforce_account_name_match = enforce_account_name_match
        kwargs['instance'] = None
        if self.user:
            kwargs['instance'] = self.user.event_profile(self.event)
        super().__init__(*args, **kwargs, event=self.event, limit_to_rooms=True)
        self.speaker = self.user
        read_only = kwargs.get('read_only', False)
        initial = kwargs.get('initial', {})
        initial['name'] = name

        if not self.add_additional_speaker and 'additional_speaker' in self.fields:
            self.fields.pop('additional_speaker')
        if 'additional_speaker' in self.fields:
            self._update_cfp_texts('additional_speaker')

        if self.user:
            initial.update({field: getattr(self.user, field) for field in self.user_fields})
        for field in self.user_fields:
            field_class = self.Meta.field_classes.get(field, User._meta.get_field(field).formfield)
            field_kwargs = {
                'initial': initial.get(field),
                'disabled': read_only,
                'help_text': User._meta.get_field(field).help_text,
            }
            if field == 'avatar':
                field_kwargs['max_size'] = settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE]
            self.fields[field] = field_class(**field_kwargs)
            custom_widget_class = self.Meta.widgets.get(field)
            if custom_widget_class:
                old_widget = self.fields[field].widget
                new_widget = custom_widget_class()
                # Preserve selected attributes (such as data-maxsize, data-sizewarning, accept)
                # that may have been set on the original widget, without overriding
                # attributes defined by the new custom widget.
                for attr_name in ('data-maxsize', 'data-sizewarning', 'accept'):
                    if attr_name in old_widget.attrs and attr_name not in new_widget.attrs:
                        new_widget.attrs[attr_name] = old_widget.attrs[attr_name]
                self.fields[field].widget = new_widget
            self._update_cfp_texts(field)

        field_names = list(self.fields)
        if 'fullname' in field_names:
            field_names.remove('fullname')
            self.order_fields(['fullname'] + field_names)

        for field_name in ('fullname', 'email'):
            if field_name in self.fields:
                self.fields[field_name].required = not self.not_strict
                if hasattr(self.fields[field_name].widget, 'is_required'):
                    self.fields[field_name].widget.is_required = not self.not_strict

        cfp_defaults = default_fields()
        _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
        count_length_in = (_cfp.settings.get('count_length_in', 'chars') if _cfp else 'chars')
        count_chars = count_length_in == 'chars'
        for key in ('avatar_source', 'avatar_license', 'additional_speaker'):
            if key not in self.fields:
                continue
            default_config = cfp_defaults.get(key, {})
            config = (_cfp.fields.get(key, default_config) if _cfp else default_config)
            visibility = config.get('visibility', default_config.get('visibility', 'optional'))
            if visibility == 'do_not_ask':
                self.fields.pop(key, None)
                continue
            field = self.fields[key]
            field.required = visibility == 'required'
            if hasattr(field.widget, 'is_required'):
                field.widget.is_required = field.required
            min_value = config.get('min_length')
            max_value = config.get('max_length')
            if min_value or max_value:
                if min_value and count_chars:
                    field.widget.attrs['minlength'] = min_value
                if max_value and count_chars:
                    field.widget.attrs['maxlength'] = max_value
                field.validators.append(
                    partial(
                        self.validate_field_length,
                        min_length=min_value,
                        max_length=max_value,
                        count_in=count_length_in,
                    )
                )
                field.original_help_text = getattr(field, 'original_help_text', field.help_text)
                field.added_help_text = self.get_help_text('', min_value, max_value, count_length_in)
                field.help_text = ' '.join(
                    part for part in (field.original_help_text, field.added_help_text) if part
                )

        if not (_cfp and _cfp.request_avatar):
            self.fields.pop('avatar', None)
            self.fields.pop('avatar_source', None)
            self.fields.pop('avatar_license', None)
            self.fields.pop('get_gravatar', None)
        else:
            if not _cfp.enable_gravatar:
                self.fields.pop('get_gravatar', None)
            if 'avatar' in self.fields:
                self.fields['avatar'].required = False
                self.fields['avatar'].widget.is_required = _cfp.require_avatar and not getattr(self, 'not_strict', False)
                svg_limit = filesize(getattr(settings, 'IMAGE_SVG_MAX_SIZE', 1024 * 1024))
                self.fields['avatar'].help_text = ' '.join(
                    part
                    for part in (
                        self.fields['avatar'].help_text,
                        _('SVG files are limited to {size}.').format(size=svg_limit),
                    )
                    if part
                )

        self.inject_questions_into_fields(
            target=TalkQuestionTarget.SPEAKER,
            event=self.event,
            speaker=self.user,
            readonly=read_only,
        )

        if _cfp and _cfp.request_social_links:
            self.fields['social_links'] = forms.CharField(
                required=False,
                widget=forms.HiddenInput(),
            )

        # Reorder fields based on configuration
        self.order_fields_by_config('speaker')

        if self.is_bound and not self.is_valid() and 'availabilities' in self.errors:
            # Replace self.data with a version that uses initial["availabilities"]
            # in order to have event and timezone data available
            data = self.data.copy()
            data['availabilities'] = initial.get('availabilities', [])
            self.data = data

    @cached_property
    def user_fields(self):
        if self.user and not self.essential_only:
            return [field for field in self.USER_FIELDS if field != 'email' or self.with_email]
        return [
            field
            for field in self.USER_FIELDS
            if field not in self.FIRST_TIME_EXCLUDE and (field != 'email' or self.with_email)
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = User.objects.all()
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.filter(email__iexact=email):
            raise ValidationError(get_email_address_error())
        return email

    def clean_avatar_source(self):
        return validate_avatar_license_text(self.cleaned_data.get('avatar_source'))

    def clean_avatar_license(self):
        return validate_avatar_license_text(self.cleaned_data.get('avatar_license'))

    def clean(self):
        data = super().clean()
        _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
        if not getattr(self, 'not_strict', False) and _cfp and _cfp.require_avatar and not data.get('avatar') and not data.get('get_gravatar'):
            if _cfp.enable_gravatar:
                msg = _('Please provide a profile picture or allow us to load your picture from gravatar!')
            else:
                msg = _('Please provide a profile picture!')
            self.add_error('avatar', forms.ValidationError(msg))

        fullname = self.cleaned_data.get('fullname')
        if (
            self.enforce_account_name_match
            and self.user
            and fullname
            and self.user.fullname
            and fullname.strip() != self.user.fullname.strip()
        ):
            self.add_error(
                'fullname',
                forms.ValidationError(
                    _(
                        'The name you entered does not match the name on your account. '
                        'Please update your account name in your profile before submitting.'
                    )
                ),
            )
        return data

    def save(self, **kwargs):
        avatar_changed = 'avatar' in self.changed_data
        old_thumbnails_to_delete = []
        if avatar_changed:
            for field_name in ('avatar_thumbnail', 'avatar_thumbnail_tiny'):
                thumbnail = getattr(self.user, field_name, None)
                if thumbnail and thumbnail.name:
                    old_thumbnails_to_delete.append(thumbnail)

        for user_attribute in self.user_fields:
            value = self.cleaned_data.get(user_attribute)
            if user_attribute == 'avatar':
                if value is False:
                    self.user.avatar = None
                    self.user.avatar_thumbnail = None
                    self.user.avatar_thumbnail_tiny = None
                elif value:
                    self.user.avatar = value
                    self.user.avatar_thumbnail = None
                    self.user.avatar_thumbnail_tiny = None
            elif value is None and user_attribute == 'get_gravatar':
                # Only reset get_gravatar if the field was actually present on
                # the form (i.e. Gravatar is enabled). If the field was popped
                # because enable_gravatar is False, we must not touch the
                # user's saved preference.
                if 'get_gravatar' in self.fields:
                    self.user.get_gravatar = False
            else:
                setattr(self.user, user_attribute, value)

            # Add thumbnail fields to update_fields when avatar changes
            update_fields = [user_attribute]
            if user_attribute == 'avatar':
                update_fields.extend(['avatar_thumbnail', 'avatar_thumbnail_tiny'])
            self.user.save(update_fields=update_fields)

        self.instance.event = self.event
        self.instance.user = self.user
        result = super().save(**kwargs)

        if avatar_changed:
            if self.user.avatar:
                self.user.process_image('avatar', generate_thumbnail=True)
            for thumbnail in old_thumbnails_to_delete:
                thumbnail.delete(save=False)
        for key, value in self.cleaned_data.items():
            if key.startswith('question_'):
                self.save_questions(key, value)
        return result

    class Meta:
        model = SpeakerProfile
        fields = ('biography',)
        public_fields = ['fullname', 'biography', 'avatar']
        widgets = {
            'biography': RichTextWidget,
            'avatar': ClearableBasenameFileInput,
            'avatar_source': Textarea,
            'avatar_license': Textarea,
        }
        field_classes = {
            'avatar': ImageField,
        }
        field_classes = {
            'avatar': ImageField,
        }
        request_require = {'biography', 'availabilities'}


class OrgaProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('fullname', 'locale')


class LoginInfoForm(forms.ModelForm):
    error_messages = {'pw_current_wrong': _('The current password you entered was not correct.')}

    old_password = forms.CharField(widget=forms.PasswordInput, label=_('Password (current)'), required=True)
    password = NewPasswordField(label=phrases.base.new_password, required=False)
    password_repeat = NewPasswordConfirmationField(
        label=phrases.base.password_repeat, required=False, confirm_with='password'
    )

    def clean_old_password(self):
        old_pw = self.cleaned_data.get('old_password')
        if not check_password(old_pw, self.user.password):
            raise forms.ValidationError(self.error_messages['pw_current_wrong'], code='pw_current_wrong')
        return old_pw

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email):
            raise ValidationError(get_email_address_error())
        return email

    def clean(self):
        data = super().clean()
        password = self.cleaned_data.get('password')
        if password and password != self.cleaned_data.get('password_repeat'):
            self.add_error('password_repeat', ValidationError(phrases.base.passwords_differ))
        return data

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs['instance'] = user
        super().__init__(*args, **kwargs)

    def save(self):
        super().save()
        password = self.cleaned_data.get('password')
        if password:
            self.user.change_password(password)

    class Meta:
        model = User
        fields = ('email',)


class SpeakerInformationForm(I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields['limit_types'].queryset = event.submission_types.all()
        if not event.get_feature_flag('use_tracks'):
            self.fields.pop('limit_tracks')
        else:
            self.fields['limit_tracks'].queryset = event.tracks.all()

    def save(self, *args, **kwargs):
        self.instance.event = self.event
        return super().save(*args, **kwargs)

    class Meta:
        model = SpeakerInformation
        fields = (
            'title',
            'text',
            'target_group',
            'limit_types',
            'limit_tracks',
            'resource',
        )
        field_classes = {
            'limit_tracks': SafeModelMultipleChoiceField,
            'limit_types': SafeModelMultipleChoiceField,
            'resource': SizeFileField,
        }
        widgets = {
            'limit_tracks': EnhancedSelectMultiple(color_field='color'),
            'limit_types': EnhancedSelectMultiple,
        }


class SpeakerFilterForm(forms.Form):
    default_renderer = InlineFormLabelRenderer

    role = forms.ChoiceField(
        label=_('Role'),
        choices=(
            ('', phrases.base.all_choices),
            ('true', phrases.schedule.speakers if phrases.schedule else _('Speakers')),
            ('false', _('Non-accepted submitters')),
        ),
        required=False,
        widget=EnhancedSelect,
    )
    arrived = forms.ChoiceField(
        label=_('Arrival'),
        choices=(
            ('', phrases.base.all_choices),
            ('true', _('Marked as arrived')),
            ('false', _('Not yet arrived')),
        ),
        required=False,
        widget=EnhancedSelect,
    )
    question = SafeModelChoiceField(queryset=TalkQuestion.objects.none(), required=False, widget=forms.HiddenInput())

    def __init__(self, *args, event=None, filter_arrival=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields['question'].queryset = event.talkquestions.all()
        if not filter_arrival:
            self.fields.pop('arrived')

    def filter_queryset(self, queryset):
        data = self.cleaned_data
        if data.get('role') == 'true':
            queryset = queryset.filter(
                user__submissions__in=self.event.submissions.filter(state__in=SubmissionStates.accepted_states)
            )
        elif data.get('role') == 'false':
            queryset = queryset.exclude(
                user__submissions__in=self.event.submissions.filter(state__in=SubmissionStates.accepted_states)
            )
        if has_arrived := data.get('arrived'):
            queryset = queryset.filter(has_arrived=(has_arrived == 'true'))
        return queryset


class UserSpeakerFilterForm(forms.Form):
    default_renderer = InlineFormRenderer

    role = forms.ChoiceField(
        choices=(
            ('speaker', phrases.schedule.speakers if phrases.schedule else _('Speakers')),
            ('submitter', _('Non-accepted submitters')),
            ('all', phrases.base.all_choices),
        ),
        required=False,
        widget=EnhancedSelect,
    )
    events = SafeModelMultipleChoiceField(
        queryset=Event.objects.none(),
        required=False,
        widget=EnhancedSelectMultiple,
    )

    def __init__(self, *args, events=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = events
        if events.count() > 1:
            self.fields['events'].queryset = events
        else:
            self.fields.pop('events')

    def filter_queryset(self, queryset):
        data = self.cleaned_data
        events = data.get('events') or self.events
        role = data.get('role') or 'speaker'

        qs = (
            queryset.filter(profiles__event__in=events)
            .prefetch_related('profiles', 'profiles__event')
            .annotate(
                submission_count=Count(
                    'submissions',
                    filter=Q(submissions__event__in=events),
                    distinct=True,
                ),
                accepted_submission_count=Count(
                    'submissions',
                    filter=Q(submissions__event__in=events)
                    & Q(submissions__state__in=SubmissionStates.accepted_states),
                    distinct=True,
                ),
            )
        )
        if role == 'speaker':
            qs = qs.filter(accepted_submission_count__gt=0)
        elif role == 'submitter':
            qs = qs.filter(accepted_submission_count=0)
        qs = qs.order_by('id').distinct()
        return qs
