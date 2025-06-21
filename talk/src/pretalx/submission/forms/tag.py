from django import forms
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.forms.fields import ColorField
from pretalx.common.forms.mixins import I18nHelpText, ReadOnlyFlag
from pretalx.submission.models import Tag


class TagForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def clean_tag(self):
        tag = self.cleaned_data["tag"]
        qs = self.event.tags.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(str(tag_obj.tag) == str(tag) for tag_obj in qs):
            raise forms.ValidationError(_("You already have a tag by this name!"))
        return tag

    class Meta:
        model = Tag
        fields = ("tag", "description", "color", "public")
        field_classes = {
            "color": ColorField,
        }
