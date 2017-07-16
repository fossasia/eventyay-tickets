from django.forms import ModelForm

from pretalx.schedule.models import Schedule


class ScheduleReleaseForm(ModelForm):

    class Meta:
        model = Schedule
        fields = ('version', )
