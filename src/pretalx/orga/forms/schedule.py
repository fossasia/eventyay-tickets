from django.forms import FileField, Form, ModelForm

from pretalx.schedule.models import Schedule


class ScheduleReleaseForm(ModelForm):

    class Meta:
        model = Schedule
        fields = ('version', )


class ScheduleImportForm(Form):
    upload = FileField()

    class Meta:
        fields = ('upload', )
