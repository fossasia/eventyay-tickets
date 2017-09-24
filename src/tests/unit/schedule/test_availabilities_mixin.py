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
        assert act.start == exp.start
        assert act.end == exp.end
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
        {'start': '2017-01-01 10:00:00', 'end': '2017-01-01 12:00:00'}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 2)),
        {'start': '2017-01-01 10:00:00', 'end': '2017-01-02 00:00:00'}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1), end=datetime.datetime(2017, 1, 1, 10)),
        {'start': '2017-01-01 00:00:00', 'end': '2017-01-01 10:00:00'}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 2)),
        {'start': '2017-01-01 10:00:00', 'end': '2017-01-02 00:00:00'}
    ),
    (
        Availability(start=datetime.datetime(2017, 1, 1), end=datetime.datetime(2017, 1, 2)),
        {'start': '2017-01-01', 'end': '2017-01-02'}  # all day
    ),
))
def test_serialize_availability(availabilitiesform, avail, expected):
    actual = availabilitiesform._serialize_availability(avail)
    assert actual == expected


@pytest.mark.django_db
@pytest.mark.parametrize('avails,expected', (
    (
        [Availability(start=datetime.datetime(2017, 1, 1, 10, tzinfo=pytz.utc), end=datetime.datetime(2017, 1, 1, 12, tzinfo=pytz.utc))],
        '{"availabilities": [{"start": "2017-01-01 10:00:00+00:00", "end": "2017-01-01 12:00:00+00:00"}], "event": {"date_from": "2017-01-01", "date_to": "2017-01-02"}}'
    ),
    ([], '{"availabilities": [], "event": {"date_from": "2017-01-01", "date_to": "2017-01-02"}}'),
    (None, '{"availabilities": [], "event": {"date_from": "2017-01-01", "date_to": "2017-01-02"}}'),
))
def test_serialize(availabilitiesform, avails, expected):
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
    room.save()
    Availability.objects.create(
        event=availabilitiesform.event, room=room,
        start=datetime.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
        end=datetime.datetime(2017, 1, 1, 12, tzinfo=pytz.utc),
    )

    form = AvailabilitiesForm(
        event=availabilitiesform.event,
        instance=room,
    )

    form.cleaned_data = {'availabilities': form.fields['availabilities'].initial}
    form.cleaned_data['availabilities'] = form.clean_availabilities()
    form.save()

    avails = Room.objects.first().availabilities.all()
    assert len(avails) == 1
    assert avails[0].id == 2
    assert avails[0].start == datetime.datetime(2017, 1, 1, 10, tzinfo=pytz.utc)
    assert avails[0].end == datetime.datetime(2017, 1, 1, 12, tzinfo=pytz.utc)
