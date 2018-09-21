from django import forms
from django.conf import settings
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from pretalx.common.forms.utils import get_help_text
from pretalx.common.forms.widgets import CheckboxMultiDropdown
from pretalx.submission.models import Submission, SubmissionStates, SubmissionType


class InfoForm(forms.ModelForm):
    def __init__(self, event, **kwargs):
        self.event = event
        readonly = kwargs.pop('readonly', False)
        instance = kwargs.get('instance')
        initial = kwargs.pop('initial', {})
        initial['submission_type'] = getattr(
            instance, 'submission_type', self.event.cfp.default_type
        )
        initial['content_locale'] = getattr(
            instance, 'content_locale', self.event.locale
        )

        super().__init__(initial=initial, **kwargs)

        self.fields['abstract'].widget.attrs['rows'] = 2
        for key in {'abstract', 'description', 'notes', 'image', 'do_not_record'}:
            request = event.settings.get(f'cfp_request_{key}')
            require = event.settings.get(f'cfp_require_{key}')
            if not request:
                self.fields.pop(key)
            else:
                self.fields[key].required = require
                min_value = event.settings.get(f'cfp_{key}_min_length')
                max_value = event.settings.get(f'cfp_{key}_max_length')
                if min_value:
                    self.fields[key].widget.attrs[f'minlength'] = min_value
                if max_value:
                    self.fields[key].widget.attrs[f'maxlength'] = max_value
                self.fields[key].help_text = get_help_text(
                    self.fields[key].help_text, min_value, max_value
                )
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(
            event=self.event
        )
        _now = now()
        if (
            not self.event.cfp.deadline or self.event.cfp.deadline >= _now
        ):  # No global deadline or still open
            types = self.event.submission_types.exclude(deadline__lt=_now)
        else:
            types = self.event.submission_types.filter(deadline__gte=_now)
        pks = set(types.values_list('pk', flat=True))
        if instance and instance.pk:
            pks |= {instance.submission_type.pk}
        self.fields['submission_type'].queryset = self.event.submission_types.filter(
            pk__in=pks
        )

        locale_names = dict(settings.LANGUAGES)
        self.fields['content_locale'].choices = [
            (a, locale_names[a]) for a in self.event.locales
        ]

        if readonly:
            for f in self.fields.values():
                f.disabled = True

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'content_locale',
            'abstract',
            'description',
            'notes',
            'do_not_record',
            'image',
        ]


class SubmissionFilterForm(forms.Form):
    state = forms.MultipleChoiceField(
        choices=SubmissionStates.get_choices(),
        required=False,
        widget=CheckboxMultiDropdown,
    )
    submission_type = forms.MultipleChoiceField(
        required=False, widget=CheckboxMultiDropdown
    )

    def __init__(self, event, *args, **kwargs):
        self.event = event
        usable_states = kwargs.pop('usable_states', None)
        super().__init__(*args, **kwargs)
        sub_count = (
            lambda x: event.submissions(manager='all_objects').filter(state=x).count()
        )  # noqa
        type_count = (
            lambda x: event.submissions(manager='all_objects')
            .filter(submission_type=x)  # noqa
            .count()
        )
        self.fields['submission_type'].choices = [
            (sub_type.pk, f'{str(sub_type)} ({type_count(sub_type.pk)})')
            for sub_type in event.submission_types.all()
        ]
        self.fields['submission_type'].widget.attrs['title'] = _('Submission types')
        if usable_states:
            usable_states = [
                choice
                for choice in self.fields['state'].choices
                if choice[0] in usable_states
            ]
        else:
            usable_states = self.fields['state'].choices
        self.fields['state'].choices = [
            (choice[0], f'{choice[1].capitalize()} ({sub_count(choice[0])})')
            for choice in usable_states
        ]
        self.fields['state'].widget.attrs['title'] = _('Submission states')
