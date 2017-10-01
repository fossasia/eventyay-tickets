import datetime

import pytest
import pytz
from django.forms import ModelForm, ValidationError

from pretalx.person.models import User
from pretalx.schedule.forms import AvailabilitiesFormMixin
from pretalx.schedule.models import Availability, Room


class AvailabilitiesForm(AvailabilitiesFormMixin, ModelForm):
    class Meta:
        model = Room
        fields = []


@pytest.fixture
def availabilitiesform(event):
    event.date_from = datetime.date(2017, 1, 1)
    event.date_to = datetime.date(2017, 1, 2)

    return AvailabilitiesForm(
        event=event,
        instance=None,
    )


@pytest.mark.django_db
@pytest.mark.parametrize('json,error', (
    ('{{{', 'not valid json'),  # invalid json
    ('[]', 'format'),  # not a dict
    ('42', 'format'),  # not a dict
    ('{}', 'format'),  # no "availabilities"
    ('{"availabilities": {}}', 'format'),  # availabilities not a list
))
def test_parse_availabilities_json_fail(availabilitiesform, json, error):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._parse_availabilities_json(json)

    assert error in str(excinfo)


@pytest.mark.django_db
@pytest.mark.parametrize('json', (
    ('{"availabilities": []}'),
    ('{"availabilities": [1]}'),
))
def test_parse_availabilities_json_success(availabilitiesform, json):
    try:
        availabilitiesform._parse_availabilities_json(json)
    except ValidationError:
        pytest.fail("Unexpected ValidationError")


@pytest.mark.django_db
@pytest.mark.parametrize('avail', (
    ([]),  # not a dict
    (42),  # not a dict
    ({}),  # missing attributes
    ({'start': True}),  # missing attributes
    ({'end': True}),  # missing attributes
    ({'start': True, 'end': True, 'foo': True}),  # extra attributes
))
def test_validate_availability_fail_format(availabilitiesform, avail):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._validate_availability(avail)

    assert 'format' in str(excinfo)


@pytest.mark.django_db
@pytest.mark.parametrize('avail', (
    ({'start': True, 'end': True}),  # wrong type
    ({'start': '', 'end': ''}),  # empty
    ({'start': '2017', 'end': '2017'}),  # missing month
    ({'start': '2017-01-01', 'end': '2017-01-02'}),  # missing time
))
def test_validate_availability_fail_date(availabilitiesform, avail):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._validate_availability(avail)

    assert 'invalid date' in str(excinfo)


@pytest.mark.django_db
@pytest.mark.parametrize('avail', (
    ({'start': '2017-01-03 01:00:00', 'end': '2017-01-03 02:00:00'}),  # both
    ({'start': '2016-12-31 23:00:00', 'end': '2017-01-01 02:00:00'}),  # start
    ({'start': '2017-01-01 10:00:00', 'end': '2017-01-03 02:00:00'}),  # end
    ({'start': '2017-01-02 00:00:00', 'end': '2017-01-03 00:00:01'}),  # end
))
def test_validate_availability_fail_timeframe(availabilitiesform, avail):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._validate_availability(avail)

    assert 'timeframe' in str(excinfo)


@pytest.mark.django_db
@pytest.mark.parametrize('avail', (
    ({'start': '2017-01-01 10:00:00', 'end': '2017-01-01 12:00:00'}),  # same day
    ({'start': '2017-01-01 10:00:00', 'end': '2017-01-02 12:00:00'}),  # next day
    ({'start': '2017-01-01 00:00:00', 'end': '2017-01-02 00:00:00'}),  # all day start
    ({'start': '2017-01-02 00:00:00', 'end': '2017-01-03 00:00:00'}),  # all day end
))
def test_validate_availability_success(availabilitiesform, avail):
    try:
        availabilitiesform._validate_availability(avail)
    except ValidationError:
        pytest.fail("Unexpected ValidationError")


@pytest.mark.django_db
@pytest.mark.parametrize('avail', (
    ({'start': '2017-01-01 00:00:00', 'end': '2017-01-01 08:00:00'}),  # local time, start
    ({'start': '2017-01-02 05:00:00', 'end': '2017-01-03 00:00:00'}),  # local time, end
    ({'start': '2017-01-01 00:00:00-05:00', 'end': '2017-01-01 00:00:00-05:00'}),  # explicit timezone, start
    ({'start': '2017-01-02 05:00:00-05:00', 'end': '2017-01-03 00:00:00-05:00'}),  # explicit timezone, end
    ({'start': '2017-01-01 05:00:00+00:00', 'end': '2017-01-01 00:00:00-05:00'}),  # UTC, start
    ({'start': '2017-01-02 05:00:00-00:00', 'end': '2017-01-03 05:00:00-00:00'}),  # UTC, end
))
def test_validate_availability_tz_success(availabilitiesform, avail):
    availabilitiesform.event.timezone = 'America/New_York'
    availabilitiesform.event.save()

    try:
        availabilitiesform._validate_availability(avail)
    except ValidationError:
        pytest.fail("Unexpected ValidationError")


@pytest.mark.django_db
@pytest.mark.parametrize('avail', (
    ({'start': '2016-12-31 23:00:00', 'end': '2017-01-01 08:00:00'}),  # local time, start
    ({'start': '2017-01-02 05:00:00', 'end': '2017-01-03 00:01:00'}),  # local time, end
    ({'start': '2016-12-31 23:00:00-05:00', 'end': '2017-01-01 00:00:00-05:00'}),  # explicit timezone, start
    ({'start': '2017-01-02 05:00:00-05:00', 'end': '2017-01-03 00:00:01-05:00'}),  # explicit timezone, end
    ({'start': '2017-01-01 04:00:00+00:00', 'end': '2017-01-01 00:00:00-05:00'}),  # UTC, start
    ({'start': '2017-01-02 05:00:00-00:00', 'end': '2017-01-03 06:00:00-00:00'}),  # UTC, end
))
def test_validate_availability_tz_fail(availabilitiesform, avail):
    availabilitiesform.event.timezone = 'America/New_York'
    availabilitiesform.event.save()

    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._validate_availability(avail)


@pytest.mark.django_db
@pytest.mark.parametrize('strdate,expected', (
    ('2017-01-01 10:00:00', datetime.datetime(2017, 1, 1, 10)),
    ('2017-01-01 10:00:00-05:00', datetime.datetime(2017, 1, 1, 10)),
    ('2017-01-01 10:00:00-04:00', datetime.datetime(2017, 1, 1, 9)),
))
def test_parse_datetime(availabilitiesform, strdate, expected):
    availabilitiesform.event.timezone = 'America/New_York'
    availabilitiesform.event.save()

    expected = pytz.timezone('America/New_York').localize(expected)
    actual = availabilitiesform._parse_datetime(strdate)

    assert actual == expected


@pytest.mark.django_db
@pytest.mark.parametrize('json,error', (
    ('{"availabilities": [{"start": "2017-01-01 10:00:00", "end": "2017-01-03 12:00:00"}]}', 'timeframe'),
    ('{{', 'not valid json'),
    ('{"availabilities": [1]}', 'format'),
))
def test_clean_availabilities_fail(availabilitiesform, json, error):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform.cleaned_data = {'availabilities': json}
        availabilitiesform.clean_availabilities()

    assert error in str(excinfo)


@pytest.mark.django_db
@pytest.mark.parametrize('json,expected', (
    ('{"availabilities": []}', []),
    (
        '{"availabilities": [{"start": "2017-01-01 10:00:00", "end": "2017-01-01 12:00:00"},'
        '{"start": "2017-01-02 11:00:00", "end": "2017-01-02 13:00:00"}]}',
        [
            Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 12)),
            Availability(start=datetime.datetime(2017, 1, 2, 11), end=datetime.datetime(2017, 1, 2, 13)),
        ]
    ),
))
def test_clean_availabilities_success(availabilitiesform, json, expected):
    availabilitiesform.cleaned_data = {'availabilities': json}
    actual = availabilitiesform.clean_availabilities()

    assert len(actual) == len(expected)

    for act, exp in zip(actual, expected):
        assert act.start.replace(tzinfo=None) == exp.start
        assert act.end.replace(tzinfo=None) == exp.end
        assert act.event_id == availabilitiesform.event.id
        assert act.id is None


@pytest.mark.django_db
@pytest.mark.parametrize('instancegen,fk_name', (
    (lambda event_id: Room.objects.create(event_id=event_id), "room_id"),
    (lambda event_id: User.objects.create_user(nick="testy"), "person_id"),
))
def test_set_foreignkeys(availabilitiesform, instancegen, fk_name):
    availabilities = [
        Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 12)),
        Availability(start=datetime.datetime(2017, 1, 2, 10), end=datetime.datetime(2017, 1, 2, 15)),
    ]
    instance = instancegen(availabilitiesform.event.id)
    availabilitiesform._set_foreignkeys(instance, availabilities)

    for avail in availabilities:
        assert getattr(avail, fk_name) == instance.id


@pytest.mark.django_db
def test_replace_availabilities(availabilitiesform):
    instance = Room.objects.create(event_id=availabilitiesform.event.id)
    Availability.objects.bulk_create([
        Availability(
            room_id=instance.id, event_id=availabilitiesform.event.id,
            start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 12)
        ),
        Availability(
            room_id=instance.id, event_id=availabilitiesform.event.id,
            start=datetime.datetime(2017, 1, 2, 10), end=datetime.datetime(2017, 1, 2, 15)
        ),
    ])

    expected = [
        Availability(
            room_id=instance.id, event_id=availabilitiesform.event.id,
            start=datetime.datetime(2017, 1, 1, 12, tzinfo=pytz.utc), end=datetime.datetime(2017, 1, 1, 12)
        ),
        Availability(
            room_id=instance.id, event_id=availabilitiesform.event.id,
            start=datetime.datetime(2017, 1, 2, 12, tzinfo=pytz.utc), end=datetime.datetime(2017, 1, 2, 15)
        ),
    ]

    availabilitiesform._replace_availabilities(instance, expected)

    actual = instance.availabilities.all()
    for act, exp in zip(actual, expected):
        assert act.start == exp.start


@pytest.mark.django_db
@pytest.mark.parametrize('avail,expected', (
    (
        Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 12)),
        {'start': '2017-01-01 10:00:00', 'end': '2017-01-01 12:00:00', 'allDay': False}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 2)),
        {'start': '2017-01-01 10:00:00', 'end': '2017-01-02 00:00:00', 'allDay': False}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1), end=datetime.datetime(2017, 1, 1, 10)),
        {'start': '2017-01-01 00:00:00', 'end': '2017-01-01 10:00:00', 'allDay': False}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 2)),
        {'start': '2017-01-01 10:00:00', 'end': '2017-01-02 00:00:00', 'allDay': False}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1), end=datetime.datetime(2017, 1, 2)),
        {'start': '2017-01-01 00:00:00', 'end': '2017-01-02 00:00:00', 'allDay': True}
    ),
))
def test_serialize_availability(availabilitiesform, avail, expected):
    actual = avail.serialize()
    del actual['id']
    assert actual == expected


@pytest.mark.django_db
@pytest.mark.parametrize('avails,expected,tzname', (
    (
        [Availability(start=datetime.datetime(2017, 1, 1, 10, tzinfo=pytz.utc), end=datetime.datetime(2017, 1, 1, 12, tzinfo=pytz.utc))],
        '{"availabilities": [{"id": 1, "start": "2017-01-01 10:00:00+00:00", "end": "2017-01-01 12:00:00+00:00", "allDay": false}], "event": {"timezone": "UTC", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
        'UTC',
    ),
    (
        [],
        '{"availabilities": [], "event": {"timezone": "UTC", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
        'UTC',
    ),
    (
        None,
        '{"availabilities": [], "event": {"timezone": "UTC", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
        'UTC',
    ),
    (
        None,
        '{"availabilities": [], "event": {"timezone": "America/New_York", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
        'America/New_York',
    ),
))
def test_serialize(availabilitiesform, avails, expected, tzname):
    availabilitiesform.event.timezone = tzname
    availabilitiesform.event.save()

    if avails is not None:
        instance = Room.objects.create(event_id=availabilitiesform.event.id)
        for avail in avails:
            avail.event_id = availabilitiesform.event.id
            avail.room_id = instance.id
        Availability.objects.bulk_create(avails)
    else:
        instance = None

    actual = availabilitiesform._serialize(availabilitiesform.event, instance)
    assert actual == expected


@pytest.mark.django_db
def test_chained(availabilitiesform, room):
    """ make sure the Mixin can actually deserialize the data it serialized """
    room.event.timezone = 'America/New_York'
    tz = pytz.timezone(room.event.timezone)
    room.event.save()
    room.save()
    # normal
    Availability.objects.create(
        event=availabilitiesform.event, room=room,
        start=tz.localize(datetime.datetime(2017, 1, 1, 10)),
        end=tz.localize(datetime.datetime(2017, 1, 1, 12)),
    )
    # all day
    Availability.objects.create(
        event=availabilitiesform.event, room=room,
        start=tz.localize(datetime.datetime(2017, 1, 1)),
        end=tz.localize(datetime.datetime(2017, 1, 3)),
    )

    form = AvailabilitiesForm(
        event=availabilitiesform.event,
        instance=room,
    )

    form.cleaned_data = {'availabilities': form.fields['availabilities'].initial}
    form.cleaned_data['availabilities'] = form.clean_availabilities()
    form.save()

    avails = Room.objects.first().availabilities.all()
    assert len(avails) == 2
    assert avails[0].id == 3
    assert avails[0].start == datetime.datetime(2017, 1, 1, 15, tzinfo=pytz.utc)
    assert avails[0].end == datetime.datetime(2017, 1, 1, 17, tzinfo=pytz.utc)
    assert avails[1].id == 4
    assert avails[1].start == datetime.datetime(2017, 1, 1, 5, tzinfo=pytz.utc)
    assert avails[1].end == datetime.datetime(2017, 1, 3, 5, tzinfo=pytz.utc)
