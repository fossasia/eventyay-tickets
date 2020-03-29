from django.forms import BooleanField, ModelForm, ValidationError
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.schedule.models import Schedule


class ScheduleReleaseForm(ModelForm, I18nModelForm):
    notify_speakers = BooleanField(
        label=_("Notify speakers of changes"), required=False, initial=True
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields["version"].required = True

    def clean_version(self):
        version = self.cleaned_data.get("version")
        if self.event.schedules.filter(version__iexact=version).exists():
            raise ValidationError(
                _(
                    "This schedule version was used already, please choose a different one."
                )
            )
        return version

    class Meta:
        model = Schedule
        fields = (
            "version",
            "comment",
        )
