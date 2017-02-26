from django import forms
from django.utils.timezone import get_current_timezone_name

from pretalx.common.forms import ReadOnlyFlag
from pretalx.person.models import EventPermission, User
from pretalx.submission.models import CfP


class CfPForm(ReadOnlyFlag, forms.ModelForm):

    class Meta:
        model = CfP
        fields = [
            'headline', 'text', 'default_type',
        ]
