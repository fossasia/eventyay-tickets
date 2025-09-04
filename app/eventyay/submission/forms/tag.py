from django import forms
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from eventyay.common.forms.fields import ColorField
from eventyay.common.forms.mixins import I18nHelpText, ReadOnlyFlag
from eventyay.base.models import Tag


class TagForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def clean_tag(self):
        tag = self.cleaned_data["tag"].strip()
        qs = self.event.tags.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(tag_obj.tag == tag for tag_obj in qs):
            raise forms.ValidationError(_("You already have a tag by this name!"))
        return tag

    class Meta:
        model = Tag
        fields = ("tag", "description", "color", "is_public")
        field_classes = {
            "color": ColorField,
        }
