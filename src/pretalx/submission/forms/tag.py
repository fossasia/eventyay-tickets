from django import forms
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import I18nHelpText, ReadOnlyFlag
from pretalx.submission.models import Tag


class TagForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields["color"].widget.attrs["class"] = "colorpickerfield"

    def clean_tag(self):
        tag = self.cleaned_data["tag"]
        qs = self.event.tags.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(str(s.tag) == str(tag) for s in qs):
            raise forms.ValidationError(_("You already have a tag by this name!"))
        return tag

    class Meta:
        model = Tag
        fields = ("tag", "description", "color", "public")
