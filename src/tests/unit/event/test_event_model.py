import datetime

import pytest

from pretalx.event.models import Event


@pytest.fixture
def event():
    return Event.objects.create(
        name='Event', slug='event', subtitle='Event event', is_public=True,
        email='orga@orga.org', locale_array='en,de', locale='en',
        date_from=datetime.date.today(), date_to=datetime.date.today()
    )


@pytest.mark.django_db
@pytest.mark.parametrize('locale_array,count', (
    ('de', 1),
    ('de,en', 2),
))
def test_locales(event, locale_array, count):
    event.locale_array = locale_array
    event.save()
    assert len(event.locales) == count
    assert len(event.named_locales) == count


@pytest.mark.django_db
def test_initial_data(event):
    assert event.cfp
    assert event.cfp.default_type
    assert event.accept_template
    assert event.ack_template
    assert event.reject_template
    assert event.schedules.count()
    assert event.wip_schedule

    event.cfp.delete()
    event._build_initial_data()

    assert event.cfp
    assert event.cfp.default_type
    assert event.accept_template
    assert event.ack_template
    assert event.reject_template
    assert event.schedules.count()
    assert event.wip_schedule
