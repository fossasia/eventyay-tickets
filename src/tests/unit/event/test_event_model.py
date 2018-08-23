import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from pretalx.event.models import Event


@pytest.fixture
def event():
    return Event.objects.create(
        name='Event', slug='event', is_public=True,
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
            name='Event', slug=slug, is_public=True,
            email='orga@orga.org', locale_array='en,de', locale='en',
            date_from=datetime.date.today(), date_to=datetime.date.today()
        ).clean_fields()


@pytest.mark.django_db
def test_event_model_slug_uniqueness():
    Event.objects.create(
        name='Event', slug='slog', is_public=True,
        email='orga@orga.org', locale_array='en,de', locale='en',
        date_from=datetime.date.today(), date_to=datetime.date.today()
    )
    assert Event.objects.count() == 1
    with pytest.raises(IntegrityError):
        Event.objects.create(
            name='Event', slug='slog', is_public=True,
            email='orga@orga.org', locale_array='en,de', locale='en',
            date_from=datetime.date.today(), date_to=datetime.date.today()
        ).clean_fields()


@pytest.mark.django_db
@pytest.mark.parametrize('with_url', (True, False))
def test_event_copy_settings(event, submission_type, with_url):
    if with_url:
        event.settings.custom_domain = 'https://testeventcopysettings.example.org'
    event.settings.random_value = 'testcopysettings'
    event.accept_template.text = 'testtemplate'
    event.accept_template.save()
    new_event = Event.objects.create(
        organiser=event.organiser, locale_array='de,en',
        name='Teh Name', slug='tn', timezone='Europe/Berlin',
        email='tehname@example.org', locale='de',
        date_from=datetime.date.today(), date_to=datetime.date.today()
    )
    assert new_event.accept_template
    assert new_event.submission_types.count() == 1
    assert event.submission_types.count() == 2
    new_event.copy_data_from(event)
    assert new_event.submission_types.count() == event.submission_types.count()
    assert new_event.accept_template
    assert new_event.accept_template.text == 'testtemplate'
    assert new_event.settings.random_value == 'testcopysettings'
    assert not new_event.settings.custom_domain


@pytest.mark.django_db
def test_event_get_default_type(event):
    assert event.submission_types.count() == 1
    event._get_default_submission_type()
    assert event.submission_types.count() == 1


@pytest.mark.django_db
def test_event_urls_custom(event):
    custom = 'https://foo.bar.com'
    assert custom not in event.urls.submit.full()
    event.settings.custom_domain = custom
    assert custom in event.urls.submit.full()
    assert custom not in event.orga_urls.cfp.full()
