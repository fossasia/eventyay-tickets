from django import forms

from pretalx.common.forms import ReadOnlyFlag
from pretalx.person.models import User


class SpeakerForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = User
        fields = [
            'nick', 'first_name', 'last_name', 'email', 'send_mail',
        ]
