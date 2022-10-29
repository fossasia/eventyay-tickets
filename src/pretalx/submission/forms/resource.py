from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pretalx.common.forms.fields import SizeFileField
from pretalx.submission.models import Resource


class ResourceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = True
        self.fields["description"].widget.attrs["required"] = True

    class Meta:
        model = Resource
        fields = ["resource", "description", "link"]
        field_classes = {"resource": SizeFileField}

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        if cleaned_data.get("resource") and cleaned_data.get("link"):
            raise ValidationError(
                _("Please either provide a link or upload a file, you cannot do both!")
            )
        if not cleaned_data.get("resource") and not cleaned_data.get("link"):
            raise ValidationError(_("Please provide a link or upload a file!"))
        return cleaned_data
