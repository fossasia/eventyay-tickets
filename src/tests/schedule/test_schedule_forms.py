import datetime as dt
import json

import pytest
import pytz
from django.forms import ModelForm, ValidationError
from django.utils import timezone
from django_scopes import scope

from pretalx.person.models import SpeakerProfile
from pretalx.schedule.forms import AvailabilitiesFormMixin
from pretalx.schedule.models import Availability, Room

timezone.activate(pytz.utc)


class AvailabilitiesForm(AvailabilitiesFormMixin, ModelForm):
    class Meta:
        model = Room
        fields = []


@pytest.fixture
def availabilitiesform(event):
    event.date_from = dt.date(2017, 1, 1)
    event.date_to = dt.date(2017, 1, 2)

    return AvailabilitiesForm(event=event, instance=None,)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "json,error",
    (
        ("{{{", "not valid json"),  # invalid json
        ("[]", "format"),  # not a dict
        ("42", "format"),  # not a dict
        ("{}", "format"),  # no "availabilities"
        ('{"availabilities": {}}', "format"),  # availabilities not a list
    ),
)
def test_parse_availabilities_json_fail(availabilitiesform, json, error):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._parse_availabilities_json(json)

    assert error in str(excinfo.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "json", (('{"availabilities": []}'), ('{"availabilities": [1]}'),)
)
def test_parse_availabilities_json_success(availabilitiesform, json):
    availabilitiesform._parse_availabilities_json(json)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "avail",
    (
        ([]),  # not a dict
        (42),  # not a dict
        ({}),  # missing attributes
        ({"start": True}),  # missing attributes
        ({"end": True}),  # missing attributes
        ({"start": True, "end": True, "foo": True}),  # extra attributes
    ),
)
def test_validate_availability_fail_format(availabilitiesform, avail):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._validate_availability(avail)

    assert "format" in str(excinfo.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "avail",
    (
        ({"start": True, "end": True}),  # wrong type
        ({"start": "", "end": ""}),  # empty
        ({"start": "2017", "end": "2017"}),  # missing month
        ({"start": "2017-01-01", "end": "2017-01-02"}),  # missing time
    ),
)
def test_validate_availability_fail_date(availabilitiesform, avail):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform._validate_availability(avail)

    assert "invalid date" in str(excinfo.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "avail",
    (
        ({"start": "2017-01-01 10:00:00", "end": "2017-01-01 12:00:00"}),  # same day
        ({"start": "2017-01-01 10:00:00", "end": "2017-01-02 12:00:00"}),  # next day
        (
            {"start": "2017-01-01 00:00:00", "end": "2017-01-02 00:00:00"}
        ),  # all day start
        ({"start": "2017-01-02 00:00:00", "end": "2017-01-03 00:00:00"}),  # all day end
    ),
)
def test_validate_availability_success(availabilitiesform, avail):
    availabilitiesform._validate_availability(avail)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "avail",
    (
        (
            {"start": "2017-01-01 00:00:00", "end": "2017-01-01 08:00:00"}
        ),  # local time, start
        (
            {"start": "2017-01-02 05:00:00", "end": "2017-01-03 00:00:00"}
        ),  # local time, end
        (
            {"start": "2017-01-01 00:00:00-05:00", "end": "2017-01-01 00:00:00-05:00"}
        ),  # explicit timezone, start
        (
            {"start": "2017-01-02 05:00:00-05:00", "end": "2017-01-03 00:00:00-05:00"}
        ),  # explicit timezone, end
        (
            {"start": "2017-01-01 05:00:00+00:00", "end": "2017-01-01 00:00:00-05:00"}
        ),  # UTC, start
        (
            {"start": "2017-01-02 05:00:00-00:00", "end": "2017-01-03 05:00:00-00:00"}
        ),  # UTC, end
    ),
)
def test_validate_availability_tz_success(availabilitiesform, avail):
    availabilitiesform.event.timezone = "America/New_York"
    availabilitiesform.event.save()
    availabilitiesform._validate_availability(avail)


@pytest.mark.django_db
def test_validate_availability_daylightsaving(availabilitiesform):
    # https://github.com/pretalx/pretalx/issues/460
    availabilitiesform.event.timezone = "Europe/Berlin"
    availabilitiesform.event.date_from = dt.date(2018, 10, 22)
    availabilitiesform.event.date_to = dt.date(2018, 10, 28)
    availabilitiesform.event.save()
    availabilitiesform._validate_availability(
        ({"start": "2018-10-22 00:00:00", "end": "2018-10-29 00:00:00"})
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "strdate,expected",
    (
        ("2017-01-01 10:00:00", dt.datetime(2017, 1, 1, 10)),
        ("2017-01-01 10:00:00-05:00", dt.datetime(2017, 1, 1, 10)),
        ("2017-01-01 10:00:00-04:00", dt.datetime(2017, 1, 1, 9)),
    ),
)
def test_parse_datetime(availabilitiesform, strdate, expected):
    availabilitiesform.event.timezone = "America/New_York"
    availabilitiesform.event.save()

    expected = pytz.timezone("America/New_York").localize(expected)
    actual = availabilitiesform._parse_datetime(strdate)

    assert actual == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "json,error", (("{{", "not valid json"), ('{"availabilities": [1]}', "format"),)
)
def test_clean_availabilities_fail(availabilitiesform, json, error):
    with pytest.raises(ValidationError) as excinfo:
        availabilitiesform.cleaned_data = {"availabilities": json}
        availabilitiesform.clean_availabilities()

    assert error in str(excinfo.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "json,expected",
    (
        ('{"availabilities": []}', []),
        (
            '{"availabilities": [{"start": "2017-01-01 10:00:00", "end": "2017-01-01 12:00:00"},'
            '{"start": "2017-01-02 11:00:00", "end": "2017-01-02 13:00:00"}]}',
            [
                Availability(
                    start=dt.datetime(2017, 1, 1, 10), end=dt.datetime(2017, 1, 1, 12)
                ),
                Availability(
                    start=dt.datetime(2017, 1, 2, 11), end=dt.datetime(2017, 1, 2, 13)
                ),
            ],
        ),
    ),
)
def test_clean_availabilities_success(availabilitiesform, json, expected):
    availabilitiesform.cleaned_data = {"availabilities": json}
    actual = availabilitiesform.clean_availabilities()

    assert len(actual) == len(expected)

    for act, exp in zip(actual, expected):
        assert act.start.replace(tzinfo=None) == exp.start
        assert act.end.replace(tzinfo=None) == exp.end
        assert act.event_id == availabilitiesform.event.id
        assert act.id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "instancegen,fk_name",
    (
        (lambda event_id: Room.objects.create(event_id=event_id), "room_id"),
        (
            lambda event_id: SpeakerProfile.objects.create(event_id=event_id),
            "person_id",
        ),
    ),
)
def test_set_foreignkeys(availabilitiesform, instancegen, fk_name):
    availabilities = [
        Availability(
            start=dt.datetime(2017, 1, 1, 10), end=dt.datetime(2017, 1, 1, 12)
        ),
        Availability(
            start=dt.datetime(2017, 1, 2, 10), end=dt.datetime(2017, 1, 2, 15)
        ),
    ]
    instance = instancegen(availabilitiesform.event.id)
    availabilitiesform._set_foreignkeys(instance, availabilities)

    for avail in availabilities:
        assert getattr(avail, fk_name) == instance.id


@pytest.mark.django_db
def test_replace_availabilities(availabilitiesform):
    with scope(event=availabilitiesform.event):
        instance = Room.objects.create(event_id=availabilitiesform.event.id)
        Availability.objects.bulk_create(
            [
                Availability(
                    room_id=instance.id,
                    event_id=availabilitiesform.event.id,
                    start=dt.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
                    end=dt.datetime(2017, 1, 1, 12, tzinfo=pytz.utc),
                ),
                Availability(
                    room_id=instance.id,
                    event_id=availabilitiesform.event.id,
                    start=dt.datetime(2017, 1, 2, 10, tzinfo=pytz.utc),
                    end=dt.datetime(2017, 1, 2, 15, tzinfo=pytz.utc),
                ),
            ]
        )

        expected = [
            Availability(
                room_id=instance.id,
                event_id=availabilitiesform.event.id,
                start=dt.datetime(2017, 1, 1, 12, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 1, 12, tzinfo=pytz.utc),
            ),
            Availability(
                room_id=instance.id,
                event_id=availabilitiesform.event.id,
                start=dt.datetime(2017, 1, 2, 12, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 2, 15, tzinfo=pytz.utc),
            ),
        ]

        availabilitiesform._replace_availabilities(instance, expected)

        actual = instance.availabilities.all()
        for act, exp in zip(actual, expected):
            assert act.start == exp.start


@pytest.mark.django_db
@pytest.mark.parametrize(
    "avail,expected",
    (
        (
            Availability(
                start=dt.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 1, 12, tzinfo=pytz.utc),
            ),
            {
                "start": "2017-01-01T10:00:00Z",
                "end": "2017-01-01T12:00:00Z",
                "allDay": False,
            },
        ),
        (
            Availability(
                start=dt.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 2, tzinfo=pytz.utc),
            ),
            {
                "start": "2017-01-01T10:00:00Z",
                "end": "2017-01-02T00:00:00Z",
                "allDay": False,
            },
        ),
        (
            Availability(
                start=dt.datetime(2017, 1, 1, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
            ),
            {
                "start": "2017-01-01T00:00:00Z",
                "end": "2017-01-01T10:00:00Z",
                "allDay": False,
            },
        ),
        (
            Availability(
                start=dt.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 2, tzinfo=pytz.utc),
            ),
            {
                "start": "2017-01-01T10:00:00Z",
                "end": "2017-01-02T00:00:00Z",
                "allDay": False,
            },
        ),
        (
            Availability(
                start=dt.datetime(2017, 1, 1, tzinfo=pytz.utc),
                end=dt.datetime(2017, 1, 2, tzinfo=pytz.utc),
            ),
            {
                "start": "2017-01-01T00:00:00Z",
                "end": "2017-01-02T00:00:00Z",
                "allDay": True,
            },
        ),
    ),
)
def test_serialize_availability(availabilitiesform, avail, expected):
    with timezone.override(pytz.utc):
        actual = avail.serialize()
    del actual["id"]
    assert actual == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "avails,expected,tzname",
    (
        (
            [
                Availability(
                    start=dt.datetime(2017, 1, 1, 10, tzinfo=pytz.utc),
                    end=dt.datetime(2017, 1, 1, 12, tzinfo=pytz.utc),
                )
            ],
            '{"availabilities": [{"id": 1, "start": "2017-01-01T10:00:00Z", "end": "2017-01-01T12:00:00Z", "allDay": false}], "event": {"timezone": "UTC", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
            "UTC",
        ),
        (
            [],
            '{"availabilities": [], "event": {"timezone": "UTC", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
            "UTC",
        ),
        (
            None,
            '{"availabilities": [], "event": {"timezone": "UTC", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
            "UTC",
        ),
        (
            None,
            '{"availabilities": [], "event": {"timezone": "America/New_York", "date_from": "2017-01-01", "date_to": "2017-01-02"}}',
            "America/New_York",
        ),
    ),
)
def test_serialize(availabilitiesform, avails, expected, tzname):
    with scope(event=availabilitiesform.event), timezone.override(pytz.utc):
        availabilitiesform.event.timezone = tzname
        availabilitiesform.event.save()

        if avails is not None:
            instance = Room.objects.create(event_id=availabilitiesform.event.id)
            for avail in avails:
                avail.event_id = availabilitiesform.event.id
                avail.room_id = instance.id
                avail.save()
        else:
            instance = None

        if avails:
            expected = json.loads(expected)
            for a, j in zip(avails, expected["availabilities"]):
                j["id"] = a.pk
            expected = json.dumps(expected)

        actual = availabilitiesform._serialize(availabilitiesform.event, instance)
        assert actual == expected


@pytest.mark.django_db
def test_chained(availabilitiesform, room):
    """make sure the Mixin can actually deserialize the data it serialized."""
    with scope(event=room.event):
        room.event.timezone = "America/New_York"
        tz = pytz.timezone(room.event.timezone)
        room.event.save()
        room.save()
        # normal
        Availability.objects.create(
            event=availabilitiesform.event,
            room=room,
            start=tz.localize(dt.datetime(2017, 1, 1, 10)),
            end=tz.localize(dt.datetime(2017, 1, 1, 12)),
        )
        # all day
        Availability.objects.create(
            event=availabilitiesform.event,
            room=room,
            start=tz.localize(dt.datetime(2017, 1, 1)),
            end=tz.localize(dt.datetime(2017, 1, 3)),
        )

        form = AvailabilitiesForm(event=availabilitiesform.event, instance=room,)

        form.cleaned_data = form.initial
        form.cleaned_data["availabilities"] = form.clean_availabilities()
        form.save()

        avails = Room.objects.first().availabilities.order_by("-start")
        assert len(avails) == 2
        assert avails[0].start == dt.datetime(2017, 1, 1, 15, tzinfo=pytz.utc)
        assert avails[0].end == dt.datetime(2017, 1, 1, 17, tzinfo=pytz.utc)
        assert avails[1].start == dt.datetime(2017, 1, 1, 5, tzinfo=pytz.utc)
        assert avails[1].end == dt.datetime(2017, 1, 3, 5, tzinfo=pytz.utc)
