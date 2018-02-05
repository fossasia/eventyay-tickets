from django import forms
from django.conf import settings
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from pretalx.submission.models import Submission, SubmissionType


class InfoForm(forms.ModelForm):

    def __init__(self, event, **kwargs):
        self.event = event
        readonly = kwargs.pop('readonly', False)

        super().__init__(**kwargs)
        instance = kwargs.get('instance')
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=self.event)
        self.initial['submission_type'] = getattr(instance, 'submission_type', self.event.cfp.default_type)
        _now = now()
        if not self.event.cfp.deadline or self.event.cfp.deadline >= _now:  # No global deadline or still open
            types = self.event.submission_types.exclude(deadline__lt=_now)
        else:
            types = self.event.submission_types.filter(deadline__gte=_now)
        pks = set(types.values_list('pk', flat=True))
        if instance and instance.pk:
            pks |= {instance.submission_type.pk, }

        self.fields['submission_type'].queryset = self.event.submission_types.filter(pk__in=pks)

        locale_names = dict(settings.LANGUAGES)
        self.fields['content_locale'].choices = [(a, locale_names[a]) for a in self.event.locales]
        if readonly:
            for f in self.fields.values():
                f.disabled = True

    class Meta:
        model = Submission
        fields = [
            'title', 'submission_type', 'content_locale', 'abstract',
            'description', 'notes', 'do_not_record', 'image',
        ]


class SubmissionFilterForm(forms.ModelForm):

    def __init__(self, event, *args, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields['submission_type'].queryset = self.fields['submission_type'].queryset.filter(event=event)
        self.fields['submission_type'].required = False
        self.fields['state'].required = False
        self.fields['state'].choices = [('', _('All states'))] + self.fields['state'].choices
        self.fields['state'].initial = ''

    class Meta:
        model = Submission
        fields = [
            'submission_type', 'state',
        ]
