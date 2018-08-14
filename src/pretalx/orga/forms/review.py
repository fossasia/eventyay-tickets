from django import forms
from django.utils.translation import ngettext_lazy, ugettext_lazy as _

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.common.phrases import phrases
from pretalx.submission.models import Review


class ReviewForm(ReadOnlyFlag, forms.ModelForm):
    def __init__(self, event, user, *args, instance=None, **kwargs):
        self.event = event
        remaining_votes = user.remaining_override_votes(event)
        self.may_override = event.settings.allow_override_votes and remaining_votes
        self.may_override = self.may_override or (
            instance and instance.override_vote is not None
        )
        self.min_value = int(event.settings.review_min_score)
        self.max_value = int(event.settings.review_max_score)
        if instance:
            if instance.override_vote is True:
                instance.score = self.max_value + 1
            elif instance.override_vote is False:
                instance.score = self.min_value - 1

        super().__init__(*args, instance=instance, **kwargs)
        choices = (
            [(None, _('No score'))] if not event.settings.review_score_mandatory else []
        )
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

        self.fields['score'] = forms.ChoiceField(
            choices=choices,
            required=event.settings.review_score_mandatory,
            disabled=kwargs.get('read_only', False),
            help_text=ngettext_lazy(
                'You have {count} override vote left.',
                'You have {count} override votes left.',
                remaining_votes,
            ).format(count=remaining_votes)
            if remaining_votes
            else '',
        )
        self.fields['text'].widget.attrs['rows'] = 2
        self.fields['text'].widget.attrs['placeholder'] = phrases.orga.example_review
        self.fields['text'].required = event.settings.review_text_mandatory

    def clean_score(self):
        score = self.cleaned_data.get('score')
        score = int(score) if score else None
        if score and not self.min_value <= score <= self.max_value:
            if not (
                (score == self.min_value - 1 or score == self.max_value + 1)
                and self.may_override
            ):
                raise forms.ValidationError(
                    _(
                        f'Please assign a score between {self.min_value} and {self.max_value}!'
                    )
                )
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
        fields = ('text', 'score')
