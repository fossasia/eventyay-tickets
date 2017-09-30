import datetime
import json

import django.forms as forms
import pytz
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nModelForm

from pretalx.common.forms import ReadOnlyFlag
from pretalx.schedule.models import Availability, Room


class AvailabilitiesFormMixin(forms.Form):
    availabilities = forms.CharField(
        label=_('Availability'),
        help_text=_('When can you use this room for your conference?'),
        widget=forms.TextInput(attrs={'class': 'availabilities-editor-data'}),
    )

    def _serialize(self, event, instance):
        if instance:
            availabilities = [
                avail.serialize()
                for avail in instance.availabilities.all()
            ]
        else:
            availabilities = []

        return json.dumps({
            'availabilities': availabilities,
            'event': {
                'timezone': event.timezone,
                'date_from': str(event.date_from),
                'date_to': str(event.date_to),
            }
        })

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        super().__init__(*args, **kwargs)
        self.fields['availabilities'].initial = self._serialize(self.event, kwargs['instance'])

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
            assert len(rawavail) == 2
            assert 'start' in rawavail
            assert 'end' in rawavail
        except AssertionError:
            raise forms.ValidationError("Submitted availability does not comply with format.")

        try:
            rawavail['start'] = self._parse_datetime(rawavail['start'])
            rawavail['end'] = self._parse_datetime(rawavail['end'])
        except (AssertionError, TypeError, ValueError):
            raise forms.ValidationError("Submitted availability contains an invalid date.")

        try:
            assert rawavail['start'].date() >= self.event.date_from
            assert rawavail['end'].date() <= self.event.date_to or (
                rawavail['end'].date() == self.event.date_to + datetime.timedelta(days=1) and
                rawavail['end'].time() == datetime.time()
            )
        except AssertionError:
            raise forms.ValidationError("Submitted availability is not within the event timeframe.")

    def clean_availabilities(self):
        rawavailabilities = self._parse_availabilities_json(self.cleaned_data['availabilities'])
        availabilities = []

        for rawavail in rawavailabilities:
            self._validate_availability(rawavail)
            availabilities.append(Availability(event_id=self.event.id, **rawavail))

        return availabilities

    def _set_foreignkeys(self, instance, availabilities):
        """
        Set the reference to `instance` in each given availability. For example,
        set the availabilitiy.room_id to instance.id, in case instance of type Room.
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

        self._set_foreignkeys(instance, availabilities)
        self._replace_availabilities(instance, availabilities)

        return instance


class RoomForm(AvailabilitiesFormMixin, ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = Room
        fields = ['name', 'description', 'capacity', 'position']
