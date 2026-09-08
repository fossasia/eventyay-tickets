from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.common.forms.mixins import ReadOnlyFlag
from eventyay.common.forms.renderers import InlineFormRenderer
from eventyay.common.forms.widgets import RichTextWidget
from eventyay.agenda.feedback_access import get_feedback_anonymous_mode
from eventyay.base.models import Feedback


class FeedbackForm(ReadOnlyFlag, forms.ModelForm):
    default_renderer = InlineFormRenderer
    parent = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, talk, **kwargs):
        super().__init__(**kwargs)
        self.instance.talk = talk
        speakers = talk.speakers.all()
        self.fields['speaker'].queryset = speakers
        self.fields['speaker'].empty_label = _('Session speakers')
        self.fields['speaker'].label_from_instance = lambda obj: obj.get_display_name()
        self.fields['speaker'].help_text = ''
        if len(speakers) == 1:
            self.fields['speaker'].widget = forms.HiddenInput()
        else:
            self.fields['speaker'].widget.attrs.update(
                {
                    'class': 'form-control form-control-sm speaker-target-select',
                    'aria-label': str(_('Send to')),
                    'title': str(
                        _(
                            'Session speakers share this feedback. Choose one speaker to send it only to them.'
                        )
                    ),
                }
            )

        anonymous_mode = get_feedback_anonymous_mode(talk.event)
        if anonymous_mode == 'optional':
            self.fields['is_public'].label = _('Visible to public')
            self.fields['is_public'].help_text = _(
                'If unchecked, this feedback will only be visible to the speakers and organizers.'
            )
            self.fields['is_public'].initial = True
        elif anonymous_mode == 'always':
            self.fields['is_public'].initial = False
            self.fields['is_public'].widget = forms.HiddenInput()
        else:
            self.fields['is_public'].initial = True
            self.fields['is_public'].widget = forms.HiddenInput()

    def save(self, *args, **kwargs):
        feedback = super().save(commit=False)
        if not self.cleaned_data.get('speaker') and self.instance.talk.speakers.count() == 1:
            feedback.speaker = self.instance.talk.speakers.first()
            
        parent_id = self.cleaned_data.get('parent')
        if parent_id:
            feedback.parent_id = parent_id
            
        if kwargs.get('commit', True):
            feedback.save()
            
        return feedback

    def clean_parent(self):
        parent_id = self.cleaned_data.get('parent')
        if parent_id:
            try:
                # Scope via the talk relation to avoid cross-session replies
                # and satisfy django_scopes on Feedback queries.
                self.instance.talk.feedback.get(id=parent_id)
            except Feedback.DoesNotExist:
                raise forms.ValidationError(_('Parent feedback does not exist.'))
        return parent_id

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError(_('Rating must be between 1 and 5.'))
        return rating

    class Meta:
        model = Feedback
        fields = ['speaker', 'rating', 'review', 'is_public']
        widgets = {
            'review': RichTextWidget(attrs={'class': 'tiptap-editor'}),
            'rating': forms.RadioSelect(
                choices=[(i, str(i)) for i in range(1, 6)],
                attrs={'class': 'star-rating-input'},
            ),
        }
