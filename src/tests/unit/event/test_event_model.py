import datetime

import pytest
from django.core.exceptions import ValidationError

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


@pytest.mark.parametrize('slug', (
    '_global', '__debug__', 'api', 'csp_report', 'events', 'download',
    'healthcheck', 'jsi18n', 'locale', 'metrics', 'orga', 'redirect',
    'widget',
))
@pytest.mark.django_db
def test_event_model_slug_blacklist_validation(slug):
    with pytest.raises(ValidationError):
        Event(
            name='Event', slug=slug, subtitle='Event event', is_public=True,
            email='orga@orga.org', locale_array='en,de', locale='en',
            date_from=datetime.date.today(), date_to=datetime.date.today()
        ).clean_fields()


@pytest.mark.django_db
def test_event_model_slug_uniqueness():
    Event.objects.create(
        name='Event', slug='slog', subtitle='Event event', is_public=True,
        email='orga@orga.org', locale_array='en,de', locale='en',
        date_from=datetime.date.today(), date_to=datetime.date.today()
    )
    assert Event.objects.count() == 1
    with pytest.raises(ValidationError):
        Event.objects.create(
            name='Event', slug='slog', subtitle='Event event', is_public=True,
            email='orga@orga.org', locale_array='en,de', locale='en',
            date_from=datetime.date.today(), date_to=datetime.date.today()
        ).clean_fields()
