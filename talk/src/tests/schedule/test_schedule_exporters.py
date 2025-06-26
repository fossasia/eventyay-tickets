import datetime as dt

import pytest
from django_scopes import scope

from pretalx.schedule.exporters import ScheduleData


def test_schedule_data_empty_methods():
    assert ScheduleData(None).metadata == []
    assert ScheduleData(None).data == []


@pytest.mark.django_db
def test_schedule_data_really_early_slot(event, slot, other_slot):
    with scope(event=event):
        slot.start += dt.timedelta(days=1)
        slot.end += dt.timedelta(days=1)
        slot.save()
        assert ScheduleData(event=event, schedule=slot.schedule).data


@pytest.mark.django_db
def test_schedule_data_out_of_bounds_slot(event, slot, other_slot):
    with scope(event=event):
        slot.start -= dt.timedelta(days=1)
        slot.end -= dt.timedelta(days=1)
        slot.save()
        assert ScheduleData(event=event, schedule=slot.schedule).data


@pytest.mark.django_db
def test_schedule_data_out_of_order_slots(event, slot, other_slot):
    with scope(event=event):
        slot.start, other_slot.start = other_slot.start, slot.start
        slot.save()
        other_slot.save()
        assert ScheduleData(event=event, schedule=slot.schedule).data
