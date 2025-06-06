import os
from datetime import date

from django import forms
from django.utils.formats import get_format
from django.utils.functional import lazy
from django.utils.timezone import get_current_timezone, now
from django.utils.translation import gettext_lazy as _


class DatePickerWidget(forms.DateInput):
    def __init__(self, attrs=None, date_format=None):
        attrs = attrs or {}
        if 'placeholder' in attrs:
            del attrs['placeholder']
        date_attrs = dict(attrs)
        date_attrs.setdefault('class', 'form-control')
        date_attrs['class'] += ' datepickerfield'
        date_attrs['autocomplete'] = 'off'

        def placeholder():
            df = date_format or get_format('DATE_INPUT_FORMATS')[0]
            return (
                now()
                .replace(
                    year=2000,
                    month=12,
                    day=31,
                    hour=18,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                .strftime(df)
            )

        date_attrs['placeholder'] = lazy(placeholder, str)

        forms.DateInput.__init__(self, date_attrs, date_format)


class TimePickerWidget(forms.TimeInput):
    def __init__(self, attrs=None, time_format=None):
        attrs = attrs or {}
        if 'placeholder' in attrs:
            del attrs['placeholder']
        time_attrs = dict(attrs)
        time_attrs.setdefault('class', 'form-control')
        time_attrs['class'] += ' timepickerfield'
        time_attrs['autocomplete'] = 'off'

        def placeholder():
            tf = time_format or get_format('TIME_INPUT_FORMATS')[0]
            return now().replace(year=2000, month=1, day=1, hour=0, minute=0, second=0, microsecond=0).strftime(tf)

        time_attrs['placeholder'] = lazy(placeholder, str)

        forms.TimeInput.__init__(self, time_attrs, time_format)


class UploadedFileWidget(forms.ClearableFileInput):
    def __init__(self, *args, **kwargs):
        # Browsers can't recognize that the server already has a file uploaded
        # Don't mark this input as being required if we already have an answer
        # (this needs to be done via the attrs, otherwise we wouldn't get the "required" star on the field label)
        attrs = kwargs.get('attrs', {})
        if kwargs.get('required') and kwargs.get('initial'):
            attrs.update({'required': None})
        kwargs.update({'attrs': attrs})

        self.position = kwargs.pop('position')
        self.event = kwargs.pop('event')
        self.answer = kwargs.pop('answer')
        super().__init__(*args, **kwargs)

    class FakeFile:
        def __init__(self, file, position, event, answer):
            self.file = file
            self.position = position
            self.event = event
            self.answer = answer

        def __str__(self):
            return os.path.basename(self.file.name).split('.', 1)[-1]

        @property
        def url(self):
            from pretix.base.models import OrderPosition
            from pretix.multidomain.urlreverse import eventreverse

            if isinstance(self.position, OrderPosition):
                return eventreverse(
                    self.event,
                    'presale:event.order.download.answer',
                    kwargs={
                        'order': self.position.order.code,
                        'secret': self.position.order.secret,
                        'answer': self.answer.pk,
                    },
                )
            else:
                return eventreverse(
                    self.event,
                    'presale:event.cart.download.answer',
                    kwargs={
                        'answer': self.answer.pk,
                    },
                )

    def format_value(self, value):
        if self.is_initial(value):
            return self.FakeFile(value, self.position, self.event, self.answer)


class SplitDateTimePickerWidget(forms.SplitDateTimeWidget):
    template_name = 'pretixbase/forms/widgets/splitdatetime.html'

    def __init__(
        self,
        attrs=None,
        date_format=None,
        time_format=None,
        min_date=None,
        max_date=None,
    ):
        attrs = attrs or {}
        if 'placeholder' in attrs:
            del attrs['placeholder']
        date_attrs = dict(attrs)
        time_attrs = dict(attrs)
        date_attrs.setdefault('class', 'form-control splitdatetimepart')
        time_attrs.setdefault('class', 'form-control splitdatetimepart')
        date_attrs.setdefault('autocomplete', 'off')
        time_attrs.setdefault('autocomplete', 'off')
        date_attrs['class'] += ' datepickerfield'
        time_attrs['class'] += ' timepickerfield'
        date_attrs['autocomplete'] = 'off'
        time_attrs['autocomplete'] = 'off'
        if min_date:
            date_attrs['data-min'] = (
                min_date if isinstance(min_date, date) else min_date.astimezone(get_current_timezone()).date()
            ).isoformat()
        if max_date:
            date_attrs['data-max'] = (
                max_date if isinstance(max_date, date) else max_date.astimezone(get_current_timezone()).date()
            ).isoformat()

        def date_placeholder():
            df = date_format or get_format('DATE_INPUT_FORMATS')[0]
            return (
                now()
                .replace(
                    year=2000,
                    month=12,
                    day=31,
                    hour=18,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                .strftime(df)
            )

        def time_placeholder():
            tf = time_format or get_format('TIME_INPUT_FORMATS')[0]
            return now().replace(year=2000, month=1, day=1, hour=0, minute=0, second=0, microsecond=0).strftime(tf)

        date_attrs['placeholder'] = lazy(date_placeholder, str)
        time_attrs['placeholder'] = lazy(time_placeholder, str)

        widgets = (
            forms.DateInput(attrs=date_attrs, format=date_format),
            forms.TimeInput(attrs=time_attrs, format=time_format),
        )
        # Skip one hierarchy level
        forms.MultiWidget.__init__(self, widgets, attrs)


class BusinessBooleanRadio(forms.RadioSelect):
    def __init__(self, require_business=False, attrs=None):
        self.require_business = require_business
        if self.require_business:
            choices = (('business', _('Business customer')),)
        else:
            choices = (
                ('individual', _('Individual customer')),
                ('business', _('Business customer')),
            )
        super().__init__(attrs, choices)

    def format_value(self, value):
        if self.require_business:
            return 'business'
        try:
            return {True: 'business', False: 'individual'}[value]
        except KeyError:
            return 'individual'

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if self.require_business:
            return True
        return {
            'business': True,
            True: True,
            'True': True,
            'individual': False,
            'False': False,
            False: False,
        }.get(value)
