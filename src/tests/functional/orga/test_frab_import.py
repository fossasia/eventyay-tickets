import pytest
from django.core.management import call_command

from pretalx.event.models import Event
from pretalx.schedule.models import Room, TalkSlot


@pytest.mark.django_db
def test_frab_import_minimal(superuser):
    assert Event.objects.count() == 0
    assert superuser.permissions.count() == 0

    call_command('import_schedule', 'tests/functional/fixtures/frab_schedule_minimal.xml')

    assert Room.objects.count() == 1
    assert Room.objects.all()[0].name == 'Volkskundemuseum'

    assert TalkSlot.objects.count() == 2
    assert TalkSlot.objects.order_by('pk')[0].schedule.version == '1.99b 🍕'
    assert TalkSlot.objects.order_by('pk')[1].schedule.version is None

    assert Event.objects.count() == 1
    event = Event.objects.first()
    assert event.name == 'PrivacyWeek 2016'

    assert superuser.permissions.filter(event=event, is_orga=True).count() == 1

    with pytest.raises(Exception):
        call_command('import_schedule', 'tests/functional/fixtures/frab_schedule_minimal.xml')

    assert superuser.permissions.filter(event=event, is_orga=True).count() == 1
    assert Event.objects.count() == 1
    assert TalkSlot.objects.count() == 2
    assert Room.objects.count() == 1

    call_command('import_schedule', 'tests/functional/fixtures/frab_schedule_minimal_2.xml')

    assert Room.objects.count() == 1
    assert Event.objects.count() == 1
    assert superuser.permissions.filter(event=event, is_orga=True).count() == 1
    assert TalkSlot.objects.count() == 5  # 3 for the first talk, 2 for the second talk
    assert set(event.schedules.all().values_list('version', flat=True)) == set(['1.99b 🍕', '1.99c 🍕', None])
