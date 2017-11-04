from django import forms
from django.utils.translation import ugettext_lazy as _
from hierarkey.forms import HierarkeyForm
from i18nfield.forms import I18nFormMixin

from pretalx.common.forms import ReadOnlyFlag
from pretalx.submission.models import Review


class ReviewSettingsForm(I18nFormMixin, HierarkeyForm):
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

    def __init__(self, event, user, *args, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        min_value = int(event.settings.review_min_score)
        max_value = int(event.settings.review_max_score)
        choices = [(None, _('No score'))]
        for counter in range(abs(max_value - min_value) + 1):
            value = min_value + counter
            name = event.settings.get(f'review_score_name_{value}')
            if name:
                name = f'{value} (»{name}«)'
            else:
                name = value
            choices.append((value, name))

        self.fields['score'] = forms.ChoiceField(choices=choices, required=False, disabled=kwargs.get('read_only', False))
        self.fields['text'].widget.attrs['rows'] = 2

    def clean_score(self):
        score = self.cleaned_data.get('score')
        score = int(score) if score else None
        minimum = int(self.event.settings.review_min_score)
        maximum = int(self.event.settings.review_max_score)
        if score and not minimum <= score <= maximum:
            raise forms.ValidationError(_(f'Please assign a score between {minimum} and {maximum}!'))
        return score

    class Meta:
        model = Review
        fields = (
            'text', 'score'
        )
