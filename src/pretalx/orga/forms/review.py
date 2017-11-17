from django import forms
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.person.models import EventPermission
from pretalx.submission.models import Review


class ReviewPermissionForm(forms.ModelForm):

    class Meta:
        model = EventPermission
        fields = (
            'review_override_count',
        )


class ReviewSettingsForm(I18nFormMixin, HierarkeyForm):
    allow_override_votes = forms.BooleanField(
        label=_('Allow override votes'),
        help_text=_('With this setting, individual reviewers can be assigned a fixed amount of "override votes" functioning like vetos.'),
        required=False,
    )
    review_min_score = forms.IntegerField(
        label=_('Minimum score'),
        help_text=_('The minimum score reviewers can assign'),
    )
    review_max_score = forms.IntegerField(
        label=_('Maximum score'),
        help_text=_('The maximum score reviewers can assign'),
    )

    def __init__(self, obj, *args, **kwargs):
        kwargs.pop('read_only')  # added in ActionFromUrl view mixin, but not needed here.
        super().__init__(*args, obj=obj, **kwargs)
        minimum = int(obj.settings.review_min_score)
        maximum = int(obj.settings.review_max_score)
        for number in range(abs(maximum - minimum + 1)):
            index = minimum + number
            self.fields[f'review_score_name_{index}'] = forms.CharField(
                label=_('Score label ({})').format(index),
                required=False
            )

    def clean(self):
        data = self.cleaned_data
        minimum = int(data.get('review_min_score'))
        maximum = int(data.get('review_max_score'))
        if not minimum < maximum:
            raise forms.ValidationError(_('Please assign a minimum score smaller than the maximum score!'))
        return data


class ReviewForm(ReadOnlyFlag, forms.ModelForm):

    def __init__(self, event, user, *args, instance=None, **kwargs):
        self.event = event
        self.may_override = event.settings.allow_override_votes and user.remaining_override_votes(event)
        self.may_override = self.may_override or (instance and instance.override_vote is not None)
        self.min_value = int(event.settings.review_min_score)
        self.max_value = int(event.settings.review_max_score)
        if instance:
            if instance.override_vote is True:
                instance.score = self.max_value + 1
            elif instance.override_vote is False:
                instance.score = self.min_value - 1

        super().__init__(*args, instance=instance, **kwargs)
        choices = [(None, _('No score'))]
        if self.may_override:
            choices.append((self.min_value - 1, _('Negative override (Veto)')))
        for counter in range(abs(self.max_value - self.min_value) + 1):
            value = self.min_value + counter
            name = event.settings.get(f'review_score_name_{value}')
            if name:
                name = f'{value} (»{name}«)'
            else:
                name = value
            choices.append((value, name))
        if self.may_override:
            choices.append((self.max_value + 1, _('Positive override')))

        self.fields['score'] = forms.ChoiceField(choices=choices, required=False, disabled=kwargs.get('read_only', False))
        self.fields['text'].widget.attrs['rows'] = 2
        self.fields['text'].widget.attrs['placeholder'] = phrases.orga.example_review

    def clean_score(self):
        score = self.cleaned_data.get('score')
        score = int(score) if score else None
        if score and not self.min_value <= score <= self.max_value:
            if not ((score == self.min_value - 1 or score == self.max_value + 1) and self.may_override):
                raise forms.ValidationError(_(f'Please assign a score between {self.min_value} and {self.max_value}!'))
        return score

    def clean(self):
        cleaned_data = super().clean()
        score = cleaned_data.get('score')
        if score == self.min_value - 1:
            cleaned_data['score'] = None
            if self.may_override:
                self.instance.override_vote = False
        elif score == self.max_value + 1:
            cleaned_data['score'] = None
            if self.may_override:
                self.instance.override_vote = True
        else:
            self.instance.override_vote = None
        if self.instance.id:
            self.instance.save()

    class Meta:
        model = Review
        fields = (
            'text', 'score'
        )
