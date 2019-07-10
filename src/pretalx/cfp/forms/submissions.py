from django import forms
from django.utils.translation import gettext_lazy as _


class SubmissionInvitationForm(forms.Form):
    speaker = forms.EmailField(label=_('Speaker E-Mail'))
    subject = forms.CharField(label=_('Subject'))
    text = forms.CharField(widget=forms.Textarea(), label=_('Text'))

    def __init__(self, submission, speaker, *args, **kwargs):
        self.submission = submission
        initial = kwargs.get('initial', {})
        subject = _('{speaker} invites you to join their talk!').format(
            speaker=speaker.get_display_name()
        )
        initial['subject'] = f'[{submission.event.slug}] {subject}'
        initial['text'] = _(
            '''Hi!

I'd like to invite you to be a speaker in the talk

  “{title}”

at {event}. Please follow this link to join:

  {url}

I'm looking forward to it!
{speaker}'''
        ).format(
            event=submission.event.name,
            title=submission.title,
            url=submission.urls.accept_invitation.full(),
            speaker=speaker.get_display_name(),
        )
        super().__init__(*args, **kwargs)

    def save(self):
        self.submission.send_invite(
            to=self.cleaned_data['speaker'].strip(),
            subject=self.cleaned_data['subject'],
            text=self.cleaned_data['text'],
        )
