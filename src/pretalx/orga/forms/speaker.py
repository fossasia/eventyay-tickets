from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.person.models import User


class SpeakerForm(ReadOnlyFlag, forms.ModelForm):

    def clean_nick(self):
        value = self.cleaned_data['nick']
        qs = User.objects.filter(nick__iexact=value)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.count() > 0:
            raise forms.ValidationError('This nick is already in use.')
        return value

    class Meta:
        model = User
        fields = [
            'nick', 'name', 'email', 'send_mail',
        ]
