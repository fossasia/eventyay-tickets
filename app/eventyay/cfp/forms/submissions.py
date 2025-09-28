from django import forms

from eventyay.common.text.phrases import phrases


class SubmissionInvitationForm(forms.Form):
    speaker = forms.EmailField(label=phrases.cfp.speaker_email)
    subject = forms.CharField(label=phrases.base.email_subject)
    text = forms.CharField(widget=forms.Textarea(), label=phrases.base.text_body)

    def __init__(self, submission, speaker, *args, **kwargs):
        self.submission = submission
        initial = kwargs.get('initial', {})
        subject = phrases.cfp.invite_subject.format(speaker=speaker.get_display_name())
        initial['subject'] = f'[{submission.event.slug}] {subject}'
        initial['text'] = phrases.cfp.invite_text.format(
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
