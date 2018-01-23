import pytest
from django.core.management import call_command

from pretalx.event.models import Event
from pretalx.schedule.models import Room, TalkSlot


@pytest.mark.django_db
def test_frab_import_minimal():
    call_command('import_schedule', 'tests/functional/fixtures/frab_schedule_minimal.xml')

    assert Room.objects.count() == 1
    assert Room.objects.all()[0].name == 'Volkskundemuseum'

    assert TalkSlot.objects.count() == 2
    assert TalkSlot.objects.all()[0].schedule.version == '1.99b 🍕'
    assert TalkSlot.objects.all()[1].schedule.version is None

    assert Event.objects.count() == 1
    assert Event.objects.all()[0].name == 'PrivacyWeek 2016'
