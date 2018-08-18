import datetime
import json

import pytz
from django import forms
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.mixins.forms import ReadOnlyFlag
from pretalx.schedule.models import Availability, Room, TalkSlot


class AvailabilitiesFormMixin(forms.Form):
    availabilities = forms.CharField(
        label=_('Availability'),
        help_text=_(
            'Please click and drag to mark the availability during the conference.'
        ),
        widget=forms.TextInput(attrs={'class': 'availabilities-editor-data'}),
        required=False,
    )

    def _serialize(self, event, instance):
        if instance:
            availabilities = [
                avail.serialize() for avail in instance.availabilities.all()
            ]
        else:
            availabilities = []

        return json.dumps(
            {
                'availabilities': availabilities,
                'event': {
                    'timezone': event.timezone,
                    'date_from': str(event.date_from),
                    'date_to': str(event.date_to),
                },
            }
        )

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        initial = kwargs.pop('initial', dict())
        initial['availabilities'] = self._serialize(self.event, kwargs['instance'])
        if not isinstance(self, forms.BaseModelForm):
            kwargs.pop('instance')
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def _parse_availabilities_json(self, jsonavailabilities):
        try:
            rawdata = json.loads(jsonavailabilities)
        except ValueError:
            raise forms.ValidationError("Submitted availabilities are not valid json.")

        try:
            assert isinstance(rawdata, dict)
            availabilities = rawdata['availabilities']
            assert isinstance(availabilities, list)
            return availabilities
        except (ValueError, AssertionError, LookupError):
            raise forms.ValidationError("Submitted json does not comply with format.")

    def _parse_datetime(self, strdate):
        tz = pytz.timezone(self.event.timezone)

        obj = parse_datetime(strdate)
        assert obj
        if obj.tzinfo is None:
            obj = tz.localize(obj)

        return obj

    def _validate_availability(self, rawavail):
        try:
            assert isinstance(rawavail, dict)
            rawavail.pop('id', None)
            rawavail.pop('allDay', None)
            assert len(rawavail) == 2
            assert 'start' in rawavail
            assert 'end' in rawavail
        except AssertionError:
            raise forms.ValidationError(
                "Submitted availability does not comply with format."
            )

        try:
            rawavail['start'] = self._parse_datetime(rawavail['start'])
            rawavail['end'] = self._parse_datetime(rawavail['end'])
        except (AssertionError, TypeError, ValueError):
            raise forms.ValidationError(
                "Submitted availability contains an invalid date."
            )

        tz = pytz.timezone(self.event.timezone)

        try:
            timeframe_start = tz.localize(
                datetime.datetime.combine(self.event.date_from, datetime.time())
            )
            assert rawavail['start'] >= timeframe_start

            # add 1 day, not 24 hours, https://stackoverflow.com/a/25427822/2486196
            timeframe_end = datetime.datetime.combine(
                self.event.date_to, datetime.time()
            )
            timeframe_end = timeframe_end + datetime.timedelta(days=1)
            timeframe_end = tz.localize(timeframe_end, is_dst=None)
            assert rawavail['end'] <= timeframe_end
        except AssertionError:
            raise forms.ValidationError(
                "Submitted availability is not within the event timeframe."
            )

    def clean_availabilities(self):
        if self.cleaned_data['availabilities'] == '':
            return None

        rawavailabilities = self._parse_availabilities_json(
            self.cleaned_data['availabilities']
        )
        availabilities = []

        for rawavail in rawavailabilities:
            self._validate_availability(rawavail)
            availabilities.append(Availability(event_id=self.event.id, **rawavail))

        return availabilities

    def _set_foreignkeys(self, instance, availabilities):
        """
        Set the reference to `instance` in each given availability.

        For example, set the availabilitiy.room_id to instance.id, in case instance of type Room.
        """
        reference_name = instance.availabilities.field.name + '_id'

        for avail in availabilities:
            setattr(avail, reference_name, instance.id)

    def _replace_availabilities(self, instance, availabilities):
        with transaction.atomic():
            # TODO: do not recreate objects unnecessarily, give the client the IDs, so we can track modifications and leave unchanged objects alone
            instance.availabilities.all().delete()
            Availability.objects.bulk_create(availabilities)

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        availabilities = self.cleaned_data['availabilities']

        if availabilities is not None:
            self._set_foreignkeys(instance, availabilities)
            self._replace_availabilities(instance, availabilities)

        return availabilities


class RoomForm(AvailabilitiesFormMixin, ReadOnlyFlag, I18nModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = _('Room I')
        self.fields['description'].widget.attrs['placeholder'] = _(
            'Description, e.g.: Our main meeting place, Room I, enter from the right.'
        )
        self.fields['speaker_info'].widget.attrs['placeholder'] = _(
            'Information for speakers, e.g.: Projector has only HDMI input.'
        )
        self.fields['capacity'].widget.attrs['placeholder'] = '300'

    class Meta:
        model = Room
        fields = ['name', 'description', 'speaker_info', 'capacity']


class QuickScheduleForm(forms.ModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))

    def __init__(self, event, *args, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = self.event.rooms.all()
        if self.instance.start:
            self.fields['start_date'].initial = self.instance.start.date()
            self.fields['start_time'].initial = self.instance.start.time()
        else:
            self.fields['start_date'].initial = event.date_from

    def save(self):
        if not self.instance:
            raise Exception
        talk = self.instance
        tz = pytz.timezone(self.event.timezone)
        talk.start = tz.localize(
            datetime.datetime.combine(
                self.cleaned_data['start_date'], self.cleaned_data['start_time']
            )
        )
        talk.end = talk.start + datetime.timedelta(
            minutes=talk.submission.get_duration()
        )
        return super().save()

    class Meta:
        model = TalkSlot
        fields = ('room',)
